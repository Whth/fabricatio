//! The HTTP client.

use std::time::Duration;

use reqwest::{Client, Url};
use secrecy::{ExposeSecret, SecretString};

use crate::answer::{Answer, Response};
use crate::error::Error;
use crate::question::Question;
use crate::question_set::{Outcome, QuestionSet};
use crate::request::{Request, State};
use crate::retry::{RetryConfig, retry_after};

/// The environment variable [`SystemOne::from_env`] reads the API key from.
pub const API_KEY_ENV: &str = "JEVLIN_API_KEY";

/// The API's base URL.
const DEFAULT_BASE_URL: &str = "https://api.typesafe.ai";

/// The evaluation endpoint, resolved against the base URL.
const EVALUATION_PATH: &str = "/v1/systemone";

/// A client for the System One evaluation API.
///
/// It makes its calls through an HTTP client of its own, unless one was handed to
/// [`SystemOneBuilder::client`] — passing one shares its connection pool, which is what several
/// clients talking to the same host want.
///
/// The client is the crate's `client` feature, on by default: with it off, `jevlin` is the request
/// and response types alone.
#[derive(Debug, Clone)]
pub struct SystemOne {
    http: Client,
    api_key: SecretString,
    endpoint: Url,
    retry: RetryConfig,
    timeout: Option<Duration>,
}

impl SystemOne {
    /// A client for the public API, with the default retry policy.
    ///
    /// # Errors
    /// Fails when the HTTP client cannot be built, which in practice means TLS initialization.
    pub fn new(api_key: impl Into<String>) -> Result<Self, Error> {
        Self::builder(api_key).build()
    }

    /// A client whose API key comes from [`API_KEY_ENV`].
    ///
    /// # Errors
    /// Fails when the variable is unset, and as [`SystemOne::new`] otherwise.
    pub fn from_env() -> Result<Self, Error> {
        let api_key = std::env::var(API_KEY_ENV).map_err(|_| Error::MissingApiKey)?;
        Self::new(api_key)
    }

    /// A client with a custom base URL, HTTP client, retry policy, or timeout.
    pub fn builder(api_key: impl Into<String>) -> SystemOneBuilder {
        SystemOneBuilder {
            api_key: SecretString::from(api_key.into()),
            base_url: DEFAULT_BASE_URL.to_string(),
            http: None,
            retry: RetryConfig::default(),
            timeout: None,
        }
    }

    /// Evaluates every question of `request` against its state, in one call.
    ///
    /// The API evaluates the questions in parallel, so asking several costs little more than asking
    /// one. Rate limits, overloads, and transport failures are retried according to the client's
    /// [`RetryConfig`].
    ///
    /// # Errors
    /// [`Error::Invalid`] when the request breaks the API's own constraints — those are caught
    /// locally, before anything is sent.
    pub async fn evaluate(&self, request: &Request) -> Result<Response, Error> {
        request.validate()?;
        let mut attempt = 1;
        loop {
            let error = match self.send(request).await {
                Ok(response) => return Ok(response),
                Err(error) => error,
            };
            if attempt >= self.retry.max_attempts || !error.is_retryable() {
                return Err(error);
            }
            let delay = error
                .retry_after()
                .unwrap_or_else(|| self.retry.backoff(attempt));
            tokio::time::sleep(delay).await;
            attempt += 1;
        }
    }

    /// Evaluates the questions of a [`QuestionSet`] against `state`, and returns the answers.
    ///
    /// The whole set travels as one request, so the API evaluates its questions in parallel. The
    /// returned [`Outcome`] carries the answers, the model that gave them, and what they cost.
    ///
    /// ```no_run
    /// use jevlin::{Answers, Deserialize, NoulAnswer, SystemOne};
    ///
    /// #[derive(Answers, Deserialize)]
    /// struct Triage {
    ///     #[jev(noul, "Does this convey urgency?", yes = "Time-critical", no = "No urgency")]
    ///     is_urgent: NoulAnswer,
    /// }
    ///
    /// # async fn demo() -> Result<(), jevlin::Error> {
    /// let client = SystemOne::new("jev-...")?;
    /// let outcome = client
    ///     .ask::<Triage>("Help! My payouts have been failing for 3 days.")
    ///     .await?;
    /// if outcome.answers.is_urgent >= 0.9 {
    ///     println!("urgent, for {} input tokens", outcome.usage.input_tokens);
    /// }
    /// # Ok(())
    /// # }
    /// ```
    ///
    /// # Errors
    /// As [`SystemOne::evaluate`], plus [`Error::MissingAnswer`] if the answer map comes back
    /// without one of the set's questions.
    pub async fn ask<T: QuestionSet>(&self, state: impl Into<State>) -> Result<Outcome<T>, Error> {
        let response = self.evaluate(&T::request(state.into())).await?;
        let answers = response.read()?;
        Ok(Outcome {
            answers,
            model: response.model,
            usage: response.usage,
        })
    }

    /// Evaluates one question against `state`.
    ///
    /// For several questions about the same state, ask them as one [`QuestionSet`] or one
    /// [`Request`]: one request answers them in parallel.
    ///
    /// # Errors
    /// As [`SystemOne::evaluate`], plus [`Error::MissingAnswer`] if the answer map comes back
    /// without this question.
    pub async fn ask_one(
        &self,
        state: impl Into<State>,
        question: impl Into<Question>,
    ) -> Result<Answer, Error> {
        const ANSWER_ID: &str = "answer";
        let mut response = self
            .evaluate(&Request::new(state).with_question(ANSWER_ID, question))
            .await?;
        response
            .answers
            .remove(ANSWER_ID)
            .ok_or_else(|| Error::MissingAnswer {
                id: ANSWER_ID.to_string(),
            })
    }

    /// Sends one attempt and maps its outcome.
    async fn send(&self, request: &Request) -> Result<Response, Error> {
        let mut call = self
            .http
            .post(self.endpoint.clone())
            .bearer_auth(self.api_key.expose_secret())
            .json(request);
        if let Some(timeout) = self.timeout {
            call = call.timeout(timeout);
        }
        let response = call.send().await?;
        let status = response.status();
        if status.is_success() {
            return Ok(serde_json::from_str(&response.text().await?)?);
        }
        let retry_after = retry_after(response.headers());
        let body = response.text().await.unwrap_or_default();
        Err(Error::from_response(status, retry_after, body))
    }
}

/// Builds a [`SystemOne`] client.
#[derive(Debug, Clone)]
pub struct SystemOneBuilder {
    api_key: SecretString,
    base_url: String,
    http: Option<Client>,
    retry: RetryConfig,
    timeout: Option<Duration>,
}

impl SystemOneBuilder {
    /// Points the client at another host: a proxy, a staging deployment, or a test server.
    pub fn base_url(mut self, base_url: impl Into<String>) -> Self {
        self.base_url = base_url.into();
        self
    }

    /// Makes requests through an HTTP client you already have.
    ///
    /// The client is used as it is, so its connection pool, its proxy, and its TLS configuration
    /// are shared with everything else that holds it. That is the point of passing one: several
    /// clients pointed at the same host reuse the same connections instead of each opening its own.
    ///
    /// A client's configuration is fixed once it is built, so [`SystemOneBuilder::timeout`] is not
    /// lost to it: the timeout is applied to each attempt as it is sent.
    pub fn client(mut self, http: Client) -> Self {
        self.http = Some(http);
        self
    }

    /// Replaces the retry policy.
    pub fn retry(mut self, retry: RetryConfig) -> Self {
        self.retry = retry;
        self
    }

    /// Sets the timeout for a single attempt.
    pub fn timeout(mut self, timeout: Duration) -> Self {
        self.timeout = Some(timeout);
        self
    }

    /// Builds the client.
    ///
    /// # Errors
    /// Fails when the base URL is not a URL, or when the HTTP client cannot be built.
    pub fn build(self) -> Result<SystemOne, Error> {
        let invalid_base_url = |reason: String| Error::InvalidBaseUrl {
            url: self.base_url.clone(),
            reason,
        };
        let base_url =
            Url::parse(&self.base_url).map_err(|error| invalid_base_url(error.to_string()))?;
        let endpoint = base_url
            .join(EVALUATION_PATH)
            .map_err(|error| invalid_base_url(error.to_string()))?;
        let http = match self.http {
            Some(http) => http,
            None => Client::builder().build()?,
        };
        Ok(SystemOne {
            http,
            api_key: self.api_key,
            endpoint,
            retry: self.retry,
            timeout: self.timeout,
        })
    }
}
