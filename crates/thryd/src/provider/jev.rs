//! The provider for TypeSafe's Jev, served over the System One evaluation API.

use http::HeaderMap;
use reqwest::Url;
use secrecy::SecretString;
use std::sync::Arc;
use std::time::Duration;

use crate::JevModel;
use crate::model::{EvaluationModel, EvaluationRequest, EvaluationResponse};
use crate::models::openai::parse_json_response;
use crate::provider::Provider;
use crate::utils::build_headers;
use crate::{ModelName, Result, ThrydError};

/// The evaluation endpoint of the public API.
const DEFAULT_ENDPOINT: &str = "https://api.typesafe.ai/v1/systemone";

/// A provider for TypeSafe's Jev model.
///
/// Jev is not an OpenAI-compatible chat API: one call evaluates a state against a set of typed
/// questions. The models this provider builds send that request — `jevlin`'s types — through the
/// shared connection for this endpoint, under the authentication these headers carry.
///
/// Where the call goes settles where its retries happen: a rate limit comes back carrying the
/// delay the API asked for, and the router's [`RetryConfig`](crate::RetryConfig) waits it out. No
/// second retry loop, and no configuration to keep turned off.
///
/// # Example
///
/// ```ignore
/// use secrecy::SecretString;
/// use thryd::JevProvider;
///
/// let provider = JevProvider::new("typesafe", SecretString::from("jev-..."));
/// ```
pub struct JevProvider {
    name: String,
    endpoint: Url,
    api_key: SecretString,
    timeout: Option<Duration>,
}

impl JevProvider {
    /// A provider for `name`, authenticating with `api_key` against the public API.
    pub fn new(name: impl Into<String>, api_key: SecretString) -> Self {
        Self {
            name: name.into(),
            endpoint: DEFAULT_ENDPOINT
                .parse()
                .expect("the default endpoint is a URL"),
            api_key,
            timeout: None,
        }
    }

    /// A provider pointed at another host: a proxy, a staging deployment, or a test server.
    ///
    /// # Errors
    /// Fails when `endpoint` is not a URL.
    pub fn with_endpoint(
        name: impl Into<String>,
        api_key: SecretString,
        endpoint: &str,
    ) -> Result<Self> {
        Ok(Self {
            name: name.into(),
            endpoint: Url::parse(endpoint)?,
            api_key,
            timeout: None,
        })
    }

    /// Sets the timeout for a single attempt.
    pub fn with_timeout(mut self, timeout: Duration) -> Self {
        self.timeout = Some(timeout);
        self
    }

    /// Evaluates every question of `request` against its state, in one call.
    ///
    /// The API evaluates the questions in parallel, so asking several costs little more than
    /// asking one.
    ///
    /// # Errors
    /// [`ThrydError::ClientError`] when the request breaks the API's own constraints, which is
    /// caught here rather than paid for with a round trip; otherwise as [`Provider::post`], with a
    /// rate limit mapped onto [`ThrydError::RateLimitExceeded`] so the delay it asked for survives.
    pub(crate) async fn evaluate(&self, request: &EvaluationRequest) -> Result<EvaluationResponse> {
        request
            .validate()
            .map_err(|invalid| ThrydError::ClientError {
                name: self.name.clone(),
                msg: invalid.reason().to_string(),
            })?;
        let mut call = self.client()?.post(self.endpoint.clone()).json(request);
        if let Some(timeout) = self.timeout {
            call = call.timeout(timeout);
        }
        parse_json_response(
            call.send().await.map_err(ThrydError::from)?,
            self.name.as_str(),
        )
        .await
    }
}

/// Implements the [`Provider`] trait for [`JevProvider`].
impl Provider for JevProvider {
    fn provider_name(&self) -> &str {
        self.name.as_str()
    }

    fn endpoint(&self) -> Url {
        self.endpoint.clone()
    }

    fn headers(&self) -> Result<HeaderMap> {
        build_headers(&self.api_key)
    }

    fn create_evaluation_model(
        self: Arc<Self>,
        model_name: ModelName,
    ) -> Result<Box<dyn EvaluationModel>> {
        Ok(Box::new(JevModel::new(model_name, self)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::connections::CONNECTIONS_POOL;
    use jevlin::Request as JevRequest;
    use std::net::SocketAddr;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::{TcpListener, TcpStream};
    use tokio::sync::oneshot;

    /// The documented response shape: one yes/no answer, plus what it cost.
    const ANSWERED: &str = r#"{"model":"jev-1.13.0",
        "answers":{"is_urgent":{"type":"noul","noul":0.95}},
        "usage":{"input_tokens":296,"output_tokens":20}}"#;

    /// A request with one yes/no question.
    fn request() -> EvaluationRequest {
        EvaluationRequest::new("The payouts have been failing for 3 days.").with_question(
            "is_urgent",
            jevlin::Question::noul("Does this convey urgency?"),
        )
    }

    /// A provider pointed at `endpoint`, authenticating like the real one.
    fn provider(endpoint: &str) -> JevProvider {
        JevProvider::with_endpoint("typesafe", SecretString::from("jev-test"), endpoint)
            .expect("the endpoint is a URL")
    }

    /// An evaluation rides the shared connection for its endpoint, with the provider's key.
    #[tokio::test]
    async fn evaluates_through_the_pooled_connection() {
        let api = FakeApi::start(Reply::ok(ANSWERED)).await;
        let provider = provider(&api.endpoint());

        let response = provider
            .evaluate(&request())
            .await
            .expect("the evaluation succeeds");

        assert_eq!(response.model.as_str(), "jev-1.13.0");
        assert_eq!(response.noul("is_urgent"), Some(0.95));
        let recorded = api.request().await;
        let (head, body) = parts(&recorded);
        assert!(head.starts_with("POST /v1/systemone HTTP/1.1"), "{head}");
        assert_eq!(header_value(head, "authorization"), Some("Bearer jev-test"));
        assert_eq!(body["state"], "The payouts have been failing for 3 days.");
        assert_eq!(body["questions"]["is_urgent"]["type"], "noul");
        assert!(
            CONNECTIONS_POOL.get(&provider.endpoint()).is_some(),
            "the evaluation went through the pooled connection for its endpoint"
        );
    }

    /// A rate limit keeps the delay the API asked for, for the router to wait out.
    #[tokio::test]
    async fn a_rate_limit_keeps_the_delay_the_api_asked_for() {
        let api = FakeApi::start(Reply::status(429).with_retry_after(3)).await;

        let error = provider(&api.endpoint())
            .evaluate(&request())
            .await
            .expect_err("a rate limit is an error");

        assert!(
            matches!(
                &error,
                ThrydError::RateLimitExceeded {
                    wait_time_ms: 3_000
                }
            ),
            "{error}"
        );
    }

    /// A request the API rejected keeps its status, so it is not read as transient.
    #[tokio::test]
    async fn a_rejected_request_keeps_its_status() {
        for status in [401, 422] {
            let api = FakeApi::start(Reply::status(status)).await;

            let error = provider(&api.endpoint())
                .evaluate(&request())
                .await
                .expect_err("the API rejected the request");

            assert!(
                matches!(&error, ThrydError::ApiError { status: rejected, .. } if *rejected == status),
                "{error}"
            );
        }
    }

    /// A request the API would reject is caught here, so it never costs a round trip.
    #[tokio::test]
    async fn an_invalid_request_never_reaches_the_api() {
        let api = FakeApi::start(Reply::ok(ANSWERED)).await;
        let provider = provider(&api.endpoint());

        let error = provider
            .evaluate(&JevRequest::new("state"))
            .await
            .expect_err("a request with no questions is invalid");

        match error {
            ThrydError::ClientError { name, msg } => {
                assert_eq!(name, "typesafe");
                assert!(msg.contains("at least one question"), "{msg}");
            }
            other => panic!("unexpected error: {other}"),
        }
        assert!(
            CONNECTIONS_POOL.get(&provider.endpoint()).is_none(),
            "nothing was sent, so nothing is pooled"
        );
    }

    /// The configured timeout bounds a single attempt.
    #[tokio::test]
    async fn bounds_an_attempt_with_the_configured_timeout() {
        let api = FakeApi::start(Reply::ok(ANSWERED).delayed(Duration::from_secs(5))).await;

        let error = provider(&api.endpoint())
            .with_timeout(Duration::from_millis(50))
            .evaluate(&request())
            .await
            .expect_err("the attempt times out");

        match error {
            ThrydError::Reqwest(error) => assert!(error.is_timeout(), "{error}"),
            other => panic!("unexpected error: {other}"),
        }
    }

    /// One canned HTTP reply.
    struct Reply {
        status: u16,
        body: &'static str,
        retry_after: Option<u64>,
        delay: Option<Duration>,
    }

    impl Reply {
        /// The reply a successful evaluation gets.
        fn ok(body: &'static str) -> Self {
            Self::status(200).with_body(body)
        }

        /// A reply with an empty body, for the statuses a request is rejected with.
        fn status(status: u16) -> Self {
            Self {
                status,
                body: "",
                retry_after: None,
                delay: None,
            }
        }

        /// Answers with the delay the API asks for, in whole seconds.
        fn with_retry_after(mut self, seconds: u64) -> Self {
            self.retry_after = Some(seconds);
            self
        }

        /// Answers only after `delay`, so a caller's timeout becomes observable.
        fn delayed(mut self, delay: Duration) -> Self {
            self.delay = Some(delay);
            self
        }

        fn with_body(mut self, body: &'static str) -> Self {
            self.body = body;
            self
        }
    }

    /// A fake System One endpoint: it answers one request, and records what it received.
    struct FakeApi {
        addr: SocketAddr,
        received: oneshot::Receiver<String>,
    }

    impl FakeApi {
        async fn start(reply: Reply) -> Self {
            let listener = TcpListener::bind("127.0.0.1:0").await.expect("a free port");
            let addr = listener.local_addr().expect("the bound address");
            let (sender, received) = oneshot::channel();
            tokio::spawn(async move {
                let Ok((mut stream, _)) = listener.accept().await else {
                    return;
                };
                let Some(request) = read_request(&mut stream).await else {
                    return;
                };
                let _ = sender.send(request);
                let _ = respond(&mut stream, &reply).await;
            });
            Self { addr, received }
        }

        /// Where the provider under test points.
        fn endpoint(&self) -> String {
            format!("http://{}/v1/systemone", self.addr)
        }

        /// The request the server received, verbatim.
        async fn request(self) -> String {
            self.received.await.expect("the server received a request")
        }
    }

    /// Reads one whole HTTP request — head and body — off the socket.
    async fn read_request(stream: &mut TcpStream) -> Option<String> {
        let mut buffer = Vec::new();
        let mut chunk = [0_u8; 1024];
        loop {
            let read = stream.read(&mut chunk).await.ok()?;
            if read == 0 {
                return Some(String::from_utf8_lossy(&buffer).into_owned());
            }
            buffer.extend_from_slice(&chunk[..read]);
            let Some(head_end) = head_end(&buffer) else {
                continue;
            };
            let head = String::from_utf8_lossy(&buffer[..head_end]);
            let length = header_value(&head, "content-length")
                .and_then(|length| length.parse::<usize>().ok())
                .unwrap_or(0);
            if buffer.len() >= head_end + length {
                return Some(String::from_utf8_lossy(&buffer).into_owned());
            }
        }
    }

    /// Answers one request, after the delay the reply carries.
    async fn respond(stream: &mut TcpStream, reply: &Reply) -> std::io::Result<()> {
        if let Some(delay) = reply.delay {
            tokio::time::sleep(delay).await;
        }
        let mut head = format!(
            "HTTP/1.1 {} {}\r\ncontent-type: application/json\r\ncontent-length: {}\r\nconnection: close\r\n",
            reply.status,
            reason(reply.status),
            reply.body.len()
        );
        if let Some(seconds) = reply.retry_after {
            head.push_str(&format!("retry-after: {seconds}\r\n"));
        }
        head.push_str("\r\n");
        stream.write_all(head.as_bytes()).await?;
        stream.write_all(reply.body.as_bytes()).await?;
        stream.shutdown().await
    }

    fn reason(status: u16) -> &'static str {
        match status {
            200 => "OK",
            401 => "Unauthorized",
            422 => "Unprocessable Entity",
            429 => "Too Many Requests",
            529 => "Overloaded",
            _ => "Error",
        }
    }

    fn head_end(buffer: &[u8]) -> Option<usize> {
        buffer
            .windows(4)
            .position(|window| window == b"\r\n\r\n")
            .map(|index| index + 4)
    }

    /// The value of header `name` in an HTTP head, matched without case.
    fn header_value<'a>(head: &'a str, name: &str) -> Option<&'a str> {
        head.lines().find_map(|line| {
            let (key, value) = line.split_once(':')?;
            key.eq_ignore_ascii_case(name).then(|| value.trim())
        })
    }

    /// The head and the parsed JSON body of a recorded request.
    fn parts(request: &str) -> (&str, serde_json::Value) {
        let (head, body) = request
            .split_once("\r\n\r\n")
            .expect("a request has a body");
        (head, serde_json::from_str(body).expect("the body is JSON"))
    }
}
