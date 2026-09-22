//! The client over a real HTTP stack: the request it sends, and what it makes of every reply.

mod support;

use std::time::{Duration, Instant};

use jevlin::{ChoiceCriteria, Error, Question, Request, RetryConfig, SystemOne};

use support::{FakeApi, Reply, STATE, Triage, answered, header_value, parts, request, triage};

#[tokio::test]
async fn evaluates_a_question_against_the_real_endpoint_shape() {
    let api = FakeApi::start(vec![Reply::ok(&answered("is_urgent"))]).await;

    let response = api.client().evaluate(&request()).await.unwrap();

    assert_eq!(response.model.as_str(), "jev-1.13.0");
    assert_eq!(response.noul("is_urgent"), Some(0.95));
    assert_eq!(response.usage.input_tokens, 296);

    let requests = api.requests();
    assert_eq!(requests.len(), 1);
    let (head, body) = parts(&requests[0]);
    assert!(
        head.starts_with("POST /v1/systemone HTTP/1.1"),
        "unexpected request line: {head}"
    );
    assert_eq!(header_value(head, "authorization"), Some("Bearer test-key"));
    assert_eq!(
        header_value(head, "content-type"),
        Some("application/json"),
        "the API expects a JSON body"
    );
    assert_eq!(body["model"], "jev-latest");
    assert_eq!(body["state"], STATE);
    assert_eq!(body["questions"]["is_urgent"]["type"], "noul");
    assert_eq!(
        body["questions"]["is_urgent"]["instructions"],
        "Does this convey urgency?"
    );
    assert!(
        body["questions"]["is_urgent"].get("criteria").is_none(),
        "a bare question sends no criteria"
    );
}

#[tokio::test]
async fn sends_every_question_of_a_request_in_one_call() {
    let api = FakeApi::start(vec![Reply::ok(&answered("is_urgent"))]).await;

    let request = request().with_question(
        "department",
        Question::choice(
            "Which team should handle this?",
            ChoiceCriteria::new().with_option("billing", "Payments, invoicing, refunds"),
        )
        .unwrap(),
    );
    api.client().evaluate(&request).await.unwrap();

    let (_, body) = parts(&api.requests()[0]);
    assert_eq!(body["questions"].as_object().unwrap().len(), 2);
    assert_eq!(body["questions"]["department"]["type"], "choice");
}

#[tokio::test]
async fn asks_one_question_and_returns_its_answer() {
    let api = FakeApi::start(vec![Reply::ok(&answered("answer"))]).await;

    let answer = api
        .client()
        .ask_one(STATE, Question::noul("Does this convey urgency?"))
        .await
        .unwrap();

    assert_eq!(answer.as_noul().unwrap().noul, 0.95);
    let (_, body) = parts(&api.requests()[0]);
    assert_eq!(body["questions"].as_object().unwrap().len(), 1);
}

#[tokio::test]
async fn asks_a_question_set_and_returns_its_answers_with_the_usage() {
    let api = FakeApi::start(vec![Reply::ok(&triage())]).await;

    let outcome = api.client().ask::<Triage>(STATE).await.unwrap();

    assert!(outcome.answers.is_urgent >= 0.9);
    assert_eq!(outcome.answers.department, "billing");
    assert!(outcome.answers.frustration > 1.0);
    assert_eq!(outcome.model.as_str(), "jev-1.13.0");
    assert_eq!(outcome.usage.input_tokens, 296);

    let requests = api.requests();
    assert_eq!(requests.len(), 1, "the whole set travels as one request");
    let (_, body) = parts(&requests[0]);
    assert_eq!(body["questions"].as_object().unwrap().len(), 3);
    assert_eq!(body["questions"]["department"]["type"], "choice");
}

#[tokio::test]
async fn retries_a_rate_limit_and_honors_the_delay_it_asks_for() {
    let api = FakeApi::start(vec![
        Reply::error(429).with_retry_after(0),
        Reply::ok(&answered("is_urgent")),
    ])
    .await;

    let response = api.client().evaluate(&request()).await.unwrap();

    assert_eq!(response.noul("is_urgent"), Some(0.95));
    assert_eq!(api.requests().len(), 2, "the throttled attempt is retried");
}

#[tokio::test]
async fn reports_the_delay_a_rate_limit_asks_for() {
    let api = FakeApi::start(vec![Reply::error(429).with_retry_after(2)]).await;
    let retry = RetryConfig {
        max_attempts: 1,
        ..RetryConfig::default()
    };

    let error = api
        .client_with(retry)
        .evaluate(&request())
        .await
        .unwrap_err();

    assert!(
        error.is_retryable(),
        "a rate limit is worth another attempt"
    );
    assert_eq!(error.retry_after(), Some(Duration::from_secs(2)));
}

#[tokio::test]
async fn falls_back_to_its_own_backoff_for_a_retry_after_it_cannot_read() {
    let api = FakeApi::start(vec![
        Reply::error(429).with_raw_retry_after("Wed, 21 Oct 2015 07:28:00 GMT"),
        Reply::error(429).with_raw_retry_after("Wed, 21 Oct 2015 07:28:00 GMT"),
    ])
    .await;
    let backoff = Duration::from_millis(30);
    let retry = RetryConfig {
        max_attempts: 2,
        initial_backoff: backoff,
        max_backoff: backoff,
        backoff_multiplier: 2,
    };

    let started = Instant::now();
    let error = api
        .client_with(retry)
        .evaluate(&request())
        .await
        .unwrap_err();
    let elapsed = started.elapsed();

    assert!(matches!(error, Error::RateLimited { .. }), "got {error}");
    assert_eq!(api.requests().len(), 2);
    assert!(
        elapsed >= backoff,
        "an unreadable Retry-After falls back to the configured backoff, waited {elapsed:?}"
    );
}

#[tokio::test]
async fn gives_up_after_the_configured_attempts() {
    let api = FakeApi::start(vec![
        Reply::error(529).with_retry_after(0),
        Reply::error(529).with_retry_after(0),
    ])
    .await;
    let retry = RetryConfig {
        max_attempts: 2,
        ..RetryConfig::default()
    };

    let error = api
        .client_with(retry)
        .evaluate(&request())
        .await
        .unwrap_err();

    assert!(matches!(error, Error::Overloaded { .. }), "got {error:?}");
    assert!(error.is_retryable(), "an overload is worth another attempt");
    assert_eq!(api.requests().len(), 2);
}

#[tokio::test]
async fn reports_an_exhausted_key_without_retrying() {
    let api = FakeApi::start(vec![Reply::error(401)]).await;

    let error = api.client().evaluate(&request()).await.unwrap_err();

    assert!(matches!(error, Error::Unauthorized), "got {error:?}");
    assert!(!error.is_retryable(), "a bad key is not worth retrying");
    assert_eq!(error.retry_after(), None);
    assert_eq!(api.requests().len(), 1);
}

#[tokio::test]
async fn keeps_the_body_of_a_rejected_request() {
    let api = FakeApi::start(vec![Reply::error(422)]).await;

    let error = api.client().evaluate(&request()).await.unwrap_err();

    assert!(
        matches!(&error, Error::Unprocessable { detail } if detail.contains("questions")),
        "got {error:?}"
    );
    assert_eq!(api.requests().len(), 1);
}

#[tokio::test]
async fn reports_an_unexpected_status_with_its_body() {
    let api = FakeApi::start(vec![Reply::error(500)]).await;

    let error = api.client().evaluate(&request()).await.unwrap_err();

    assert!(
        matches!(&error, Error::Unexpected { status, body } if *status == 500 && body.contains("questions")),
        "got {error:?}"
    );
    assert!(!error.is_retryable(), "only 429 and 529 are throttling");
}

#[tokio::test]
async fn rejects_an_empty_request_without_a_call() {
    let api = FakeApi::start(vec![]).await;

    let error = api
        .client()
        .evaluate(&Request::new(STATE))
        .await
        .unwrap_err();

    assert!(matches!(error, Error::Invalid(_)), "got {error:?}");
    assert_eq!(error.to_string(), "a request needs at least one question");
    assert!(!error.is_retryable(), "a rejected request is never sent");
    assert!(api.requests().is_empty(), "nothing may be sent");
}

#[tokio::test]
async fn bounds_an_attempt_with_the_configured_timeout() {
    let api = FakeApi::start(vec![Reply::hang()]).await;
    let client = SystemOne::builder("test-key")
        .base_url(api.base_url.clone())
        .timeout(Duration::from_millis(50))
        .retry(RetryConfig {
            max_attempts: 1,
            ..RetryConfig::default()
        })
        .build()
        .unwrap();

    let error = client.evaluate(&request()).await.unwrap_err();

    assert!(matches!(error, Error::Transport(_)), "got {error:?}");
    assert!(
        error.is_retryable(),
        "a transport failure is worth another attempt"
    );
    assert_eq!(api.requests().len(), 1);
}

/// End to end against the real API; set `JEVLIN_API_KEY` and run
/// `cargo test -p jevlin -- --ignored`.
#[tokio::test]
#[ignore = "requires a live API key"]
async fn live_evaluation() {
    let client = SystemOne::from_env().unwrap();

    let response = client.evaluate(&request()).await.unwrap();

    let urgency = response.noul("is_urgent").expect("an answer for is_urgent");
    assert!(
        (0.0..=1.0).contains(&urgency),
        "noul is a probability, got {urgency}"
    );
    assert!(response.usage.input_tokens > 0, "the API reports usage");
}
