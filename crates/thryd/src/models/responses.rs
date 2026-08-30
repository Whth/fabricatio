//! OpenAI Responses API model implementation.
//!
//! This module provides the [`OpenaiResponsesModel`] implementation for
//! interacting with the OpenAI Responses API (`POST /v1/responses`), the
//! modern endpoint for gpt-5 and o-series reasoning models.
//!
//! Mapping from [`CompletionRequest`]:
//!
//! - `message` → `input` (plain text, or an image-parts message when
//!   `images` is non-empty)
//! - `effort` → `reasoning.effort` (non-standard values are forwarded
//!   verbatim for compatible providers)
//! - `max_completion_tokens` → `max_output_tokens`
//! - `presence_penalty` / `frequency_penalty` → unsupported by the
//!   Responses API; dropped with a warning
//!
//! # Example
//!
//! ```ignore
//! use thryd::{OpenaiResponses, CompletionRequest};
//! use secrecy::SecretString;
//! use std::sync::Arc;
//!
//! let api_key = SecretString::from("sk-...".to_string());
//! let provider = Arc::new(OpenaiResponses::new(
//!     "openai".to_string(),
//!     api_key,
//!     "https://api.openai.com/v1".parse().unwrap(),
//! ));
//! let model = provider.create_completion_model("gpt-5.2".to_string())?;
//!
//! let response = model.completion(CompletionRequest {
//!     message: "Hello, world!".to_string(),
//!     stream: false,
//!     max_completion_tokens: Some(100),
//!     effort: Some("low".to_string()),
//!     ..Default::default()
//! }).await?;
//! ```

use crate::model::{CompletionModel, CompletionRequest, Model, Usage};
use crate::models::openai::{OpenAiRoute, parse_json_response};
use crate::provider::Provider;
use crate::{CompletionResponse, ThrydError};
use async_openai::types::responses::{
    CreateResponse, CreateResponseArgs, EasyInputContent, EasyInputMessage, InputContent,
    InputImageContent, InputItem, InputParam, InputTextContent, OutputItem, OutputMessageContent,
    Reasoning, ReasoningEffort, Response, ResponseStreamEvent, Role, Status,
};
use async_trait::async_trait;
use eventsource_stream::Eventsource;
use futures::{StreamExt, TryStreamExt};
use serde_json::{Value, to_value};
use std::sync::Arc;
use tracing::*;

/// OpenAI Responses API model implementation.
///
/// This struct wraps a model name and a provider, exposing text generation
/// through the OpenAI Responses API format (`POST /v1/responses`).
///
/// # Type Parameters
///
/// - `provider: Arc<dyn Provider>` - Must be an OpenAI Responses API provider
///
/// # Example
///
/// ```ignore
/// use thryd::{OpenaiResponses, CompletionRequest};
/// use secrecy::SecretString;
/// use std::sync::Arc;
///
/// let provider = Arc::new(OpenaiResponses::new(
///     "openai".to_string(),
///     SecretString::from("sk-...".to_string()),
///     "https://api.openai.com/v1".parse().unwrap(),
/// ));
/// let model = OpenaiResponsesModel::new("gpt-5.2".to_string(), provider);
/// ```
pub struct OpenaiResponsesModel {
    /// The model name/identifier (e.g., "gpt-5.2", "o4-mini")
    name: String,
    /// The OpenAI Responses API provider to make requests through
    provider: Arc<dyn Provider>,
}

impl OpenaiResponsesModel {
    /// Creates a new `OpenaiResponsesModel` with the specified name and provider.
    ///
    /// # Arguments
    ///
    /// * `name` - The model identifier (e.g., "gpt-5.2", "o4-mini")
    /// * `provider` - An OpenAI Responses API provider instance
    pub fn new(name: String, provider: Arc<dyn Provider>) -> Self {
        Self { name, provider }
    }
}

impl Model for OpenaiResponsesModel {
    fn model_name(&self) -> &str {
        &self.name
    }

    fn provider(&self) -> Arc<dyn Provider> {
        self.provider.clone()
    }
}

/// Build the `input` field: plain text, or a user message with image parts
/// followed by the text part (mirroring the chat-completions part order).
fn build_input(request: &CompletionRequest) -> InputParam {
    if request.images.is_empty() {
        return InputParam::Text(request.message.clone());
    }
    let mut parts: Vec<InputContent> = request
        .images
        .iter()
        .map(|url| {
            InputContent::InputImage(InputImageContent {
                image_url: Some(url.clone()),
                ..Default::default()
            })
        })
        .collect();
    parts.push(InputContent::InputText(InputTextContent {
        text: request.message.clone(),
    }));
    InputParam::Items(vec![InputItem::EasyMessage(EasyInputMessage {
        role: Role::User,
        content: EasyInputContent::ContentList(parts),
        ..Default::default()
    })])
}

/// Build the serialized request body for the Responses API.
///
/// Standard effort values map to `reasoning.effort`; non-standard strings
/// are injected verbatim into the serialized JSON (for compatible providers
/// with non-standard effort values).
fn build_request_body(model_name: &str, request: &CompletionRequest) -> crate::Result<Value> {
    let effort_str = request.effort.clone();
    if request.presence_penalty.is_some() || request.frequency_penalty.is_some() {
        warn!(
            "Responses API does not support presence_penalty/frequency_penalty; \
             dropping them for model {model_name}"
        );
    }
    let reasoning_effort: Option<ReasoningEffort> = effort_str
        .as_ref()
        .and_then(|s| serde_json::from_value(serde_json::Value::String(s.clone())).ok());
    let reasoning = reasoning_effort.as_ref().map(|effort| Reasoning {
        effort: Some(effort.clone()),
        ..Default::default()
    });
    let create = CreateResponse {
        max_output_tokens: request.max_completion_tokens,
        temperature: request.temperature,
        top_p: request.top_p,
        stream: Some(request.stream),
        reasoning,
        ..CreateResponseArgs::default()
            .model(model_name)
            .input(build_input(request))
            .build()?
    };
    let mut v = to_value(create)?;
    // Fallback: if enum conversion failed but a raw effort string was provided,
    // inject it directly into the serialized JSON (for compatible providers with
    // non-standard effort values)
    if reasoning_effort.is_none()
        && let Some(s) = &effort_str
    {
        v["reasoning"]["effort"] = serde_json::Value::String(s.clone());
    }
    Ok(v)
}

/// Map Responses API usage to the router-agnostic [`Usage`].
fn response_usage(usage: Option<async_openai::types::responses::ResponseUsage>) -> Usage {
    usage
        .map(|u| Usage {
            prompt_tokens: u.input_tokens,
            completion_tokens: u.output_tokens,
            total_tokens: u.total_tokens,
        })
        .unwrap_or_default()
}

/// Extract the completion text and usage from a complete Responses API body.
///
/// Joins the text of all assistant `message` output items (the SDK-side
/// `output_text` convenience does the same). Refusal parts are logged and
/// skipped. A `failed` status is an error; an `incomplete` status keeps the
/// partial text with a warning.
fn extract_completion(response: Response) -> crate::Result<CompletionResponse> {
    match response.status {
        Status::Failed => {
            let body = match response.error {
                Some(err) => serde_json::to_string(&err)?,
                None => "unknown error".to_string(),
            };
            error!("Responses API failed: {body}");
            return Err(ThrydError::ApiError { status: 500, body });
        }
        Status::Incomplete => {
            warn!(
                "Responses API returned incomplete response: {:?}",
                response.incomplete_details
            );
        }
        _ => {}
    }
    let mut parts: Vec<String> = Vec::new();
    for item in &response.output {
        if let OutputItem::Message(message) = item {
            for content in &message.content {
                match content {
                    OutputMessageContent::OutputText(text) => parts.push(text.text.clone()),
                    OutputMessageContent::Refusal(refusal) => {
                        warn!("Responses API refusal: {}", refusal.refusal);
                    }
                }
            }
        }
    }
    let usage = response_usage(response.usage);
    Ok(CompletionResponse {
        content: parts.join(""),
        usage,
    })
}

/// Reduce a finished stream of Responses API events into one completion.
///
/// Collects `response.output_text.delta` payloads, takes usage from the
/// terminal `response.completed` (or `response.incomplete`) event, and maps
/// `response.failed` / `error` events to errors.
fn reduce_response_events(events: Vec<ResponseStreamEvent>) -> crate::Result<CompletionResponse> {
    let mut content = String::new();
    let mut usage = Usage::default();
    for event in events {
        match event {
            ResponseStreamEvent::ResponseOutputTextDelta(delta) => content.push_str(&delta.delta),
            ResponseStreamEvent::ResponseCompleted(completed) => {
                usage = response_usage(completed.response.usage);
            }
            ResponseStreamEvent::ResponseIncomplete(incomplete) => {
                warn!(
                    "Responses API stream incomplete: {:?}",
                    incomplete.response.incomplete_details
                );
                usage = response_usage(incomplete.response.usage);
            }
            ResponseStreamEvent::ResponseFailed(failed) => {
                let body = match failed.response.error {
                    Some(err) => serde_json::to_string(&err)?,
                    None => "unknown error".to_string(),
                };
                error!("Responses API stream failed: {body}");
                return Err(ThrydError::ApiError { status: 500, body });
            }
            ResponseStreamEvent::ResponseError(err) => {
                let body = serde_json::to_string(&err)?;
                error!("Responses API stream error: {body}");
                return Err(ThrydError::ApiError { status: 500, body });
            }
            _ => {}
        }
    }
    Ok(CompletionResponse { content, usage })
}

/// # Completion Implementation
///
/// Implements [`CompletionModel`] for `OpenaiResponsesModel`, providing text
/// generation through the OpenAI Responses API.
///
/// ## Streaming vs Non-Streaming
///
/// The completion request supports two modes based on the `stream` field:
///
/// - **Non-Streaming (`stream: false`)**: Waits for the complete response,
///   then returns its aggregated text with token usage.
/// - **Streaming (`stream: true`)**: Collects the `response.output_text.delta`
///   SSE events, joins them, and extracts usage from the terminal
///   `response.completed` event.
#[async_trait]
impl CompletionModel for OpenaiResponsesModel {
    async fn completion(&self, request: CompletionRequest) -> crate::Result<CompletionResponse> {
        let stream = request.stream;
        let v = build_request_body(self.model_name(), &request)?;
        trace!("Completion request: {v:?}",);

        let response = self
            .provider
            .post(OpenAiRoute::Responses.as_ref(), &v)
            .await?;
        if stream {
            let status = response.status();
            if !status.is_success() {
                let body = response.text().await.map_err(ThrydError::from)?;
                error!(
                    "API error [{}] {}: {}",
                    status.as_u16(),
                    OpenAiRoute::Responses.as_ref(),
                    body
                );
                return Err(ThrydError::ApiError {
                    status: status.as_u16(),
                    body,
                });
            }
            let events = response
                .bytes_stream()
                .eventsource()
                .map(|event| {
                    serde_json::from_str::<ResponseStreamEvent>(event?.data.as_str())
                        .map_err(ThrydError::from)
                })
                .try_collect::<Vec<ResponseStreamEvent>>()
                .await?;
            let completion = reduce_response_events(events)?;
            debug!(
                "Request tokens usages: Input {} | Output {} | Total {}",
                completion.usage.prompt_tokens,
                completion.usage.completion_tokens,
                completion.usage.total_tokens
            );
            Ok(completion)
        } else {
            let resp =
                parse_json_response::<Response>(response, OpenAiRoute::Responses.as_ref()).await?;
            let completion = extract_completion(resp)?;
            debug!(
                "Request tokens usages: Input {} | Output {} | Total {}",
                completion.usage.prompt_tokens,
                completion.usage.completion_tokens,
                completion.usage.total_tokens
            );
            Ok(completion)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn responses_route_serializes() {
        assert_eq!(OpenAiRoute::Responses.as_ref(), "responses");
        let route: OpenAiRoute = "responses".parse().unwrap();
        assert!(matches!(route, OpenAiRoute::Responses));
    }

    #[test]
    fn minimal_request_body() {
        let request = CompletionRequest {
            message: "hello".to_string(),
            stream: false,
            ..Default::default()
        };
        let v = build_request_body("gpt-5.2", &request).unwrap();
        assert_eq!(v["model"], "gpt-5.2");
        assert_eq!(v["input"], "hello");
        assert_eq!(v["stream"], false);
        assert!(v.get("temperature").is_none());
        assert!(v.get("max_output_tokens").is_none());
        assert!(v.get("reasoning").is_none());
        assert!(v.get("presence_penalty").is_none());
        assert!(v.get("frequency_penalty").is_none());
    }

    #[test]
    fn full_request_body_with_images_and_effort() {
        let request = CompletionRequest {
            message: "describe".to_string(),
            stream: true,
            top_p: Some(0.9),
            temperature: Some(0.7),
            max_completion_tokens: Some(100),
            images: vec!["data:image/png;base64,QUJD".to_string()],
            effort: Some("high".to_string()),
            ..Default::default()
        };
        let v = build_request_body("gpt-5.2", &request).unwrap();
        assert_eq!(v["stream"], true);
        assert!((v["temperature"].as_f64().unwrap() - 0.7).abs() < 1e-6);
        assert!((v["top_p"].as_f64().unwrap() - 0.9).abs() < 1e-6);
        assert_eq!(v["max_output_tokens"], 100);
        assert_eq!(v["reasoning"]["effort"], "high");
        let input = v["input"].as_array().unwrap();
        assert_eq!(input.len(), 1);
        let parts = input[0]["content"].as_array().unwrap();
        assert_eq!(parts.len(), 2);
        assert_eq!(parts[0]["type"], "input_image");
        assert_eq!(parts[0]["image_url"], "data:image/png;base64,QUJD");
        assert_eq!(parts[1]["type"], "input_text");
        assert_eq!(parts[1]["text"], "describe");
    }

    #[test]
    fn nonstandard_effort_forwarded_verbatim() {
        let request = CompletionRequest {
            message: "hello".to_string(),
            effort: Some("ultra".to_string()),
            ..Default::default()
        };
        let v = build_request_body("gpt-5.2", &request).unwrap();
        assert_eq!(v["reasoning"]["effort"], "ultra");
    }

    #[test]
    fn penalties_are_dropped() {
        let request = CompletionRequest {
            message: "hello".to_string(),
            presence_penalty: Some(0.5),
            frequency_penalty: Some(0.5),
            ..Default::default()
        };
        let v = build_request_body("gpt-5.2", &request).unwrap();
        assert!(v.get("presence_penalty").is_none());
        assert!(v.get("frequency_penalty").is_none());
    }

    #[test]
    fn extract_joins_messages_and_maps_usage() {
        let body = r#"{
            "id": "resp_abc",
            "object": "response",
            "created_at": 1750000000,
            "model": "gpt-5.2",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "id": "msg_1",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {"type": "output_text", "annotations": [], "logprobs": null, "text": "Hello"}
                    ]
                },
                {
                    "type": "message",
                    "id": "msg_2",
                    "role": "assistant",
                    "status": "completed",
                    "content": [
                        {"type": "output_text", "annotations": [], "logprobs": null, "text": " world"}
                    ]
                }
            ],
            "usage": {
                "input_tokens": 10,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens": 5,
                "output_tokens_details": {"reasoning_tokens": 2},
                "total_tokens": 15
            }
        }"#;
        let response: Response = serde_json::from_str(body).unwrap();
        let completion = extract_completion(response).unwrap();
        assert_eq!(completion.content, "Hello world");
        assert_eq!(completion.usage.prompt_tokens, 10);
        assert_eq!(completion.usage.completion_tokens, 5);
        assert_eq!(completion.usage.total_tokens, 15);
    }

    #[test]
    fn failed_response_is_error() {
        let body = r#"{
            "id": "resp_x",
            "object": "response",
            "created_at": 1750000000,
            "model": "gpt-5.2",
            "status": "failed",
            "output": [],
            "error": {"code": "server_error", "message": "boom"}
        }"#;
        let response: Response = serde_json::from_str(body).unwrap();
        let err = extract_completion(response).unwrap_err();
        assert!(err.to_string().contains("boom"));
    }

    #[test]
    fn stream_events_reduce_to_completion_with_usage() {
        let minimal_response = |status: &str, usage: bool| {
            format!(
                r#"{{
                    "id": "resp_abc",
                    "object": "response",
                    "created_at": 1750000000,
                    "model": "gpt-5.2",
                    "status": "{status}",
                    "output": []
                    {usage_tail}
                }}"#,
                usage_tail = if usage {
                    r#",
                    "usage": {
                        "input_tokens": 10,
                        "input_tokens_details": {"cached_tokens": 0},
                        "output_tokens": 5,
                        "output_tokens_details": {"reasoning_tokens": 2},
                        "total_tokens": 15
                    }"#
                } else {
                    ""
                }
            )
        };
        let events: Vec<ResponseStreamEvent> = [
            format!(
                r#"{{"type": "response.created", "sequence_number": 0, "response": {}}}"#,
                minimal_response("in_progress", false)
            ),
            r#"{"type": "response.output_text.delta", "sequence_number": 1, "item_id": "msg_1", "output_index": 0, "content_index": 0, "delta": "Hel"}"#.to_string(),
            r#"{"type": "response.output_text.delta", "sequence_number": 2, "item_id": "msg_1", "output_index": 0, "content_index": 0, "delta": "lo"}"#.to_string(),
            format!(
                r#"{{"type": "response.completed", "sequence_number": 3, "response": {}}}"#,
                minimal_response("completed", true)
            ),
        ]
        .iter()
        .map(|e| serde_json::from_str(e).unwrap())
        .collect();
        let completion = reduce_response_events(events).unwrap();
        assert_eq!(completion.content, "Hello");
        assert_eq!(completion.usage.prompt_tokens, 10);
        assert_eq!(completion.usage.completion_tokens, 5);
        assert_eq!(completion.usage.total_tokens, 15);
    }

    #[test]
    fn stream_failed_event_is_error() {
        let events: Vec<ResponseStreamEvent> = vec![
            serde_json::from_str(
                r#"{
                "type": "response.failed",
                "sequence_number": 0,
                "response": {
                    "id": "resp_x",
                    "object": "response",
                    "created_at": 1750000000,
                    "model": "gpt-5.2",
                    "status": "failed",
                    "output": [],
                    "error": {"code": "server_error", "message": "boom"}
                }
            }"#,
            )
            .unwrap(),
        ];
        let err = reduce_response_events(events).unwrap_err();
        assert!(err.to_string().contains("boom"));
    }
}
