//! A typed Rust client for TypeSafe's **Jev** model, served over the System One evaluation API.
//!
//! One call evaluates a `state` — text, or structured JSON such as a chat log, a record, or the
//! current state of your application — against a set of typed questions, and answers each of them,
//! together with the model that answered and the tokens it cost.
//!
//! The three question types are yes/no ([`Noul`]), pick-one ([`Choice`]) and rating ([`Score`]).
//! All three answer with probabilities, and pick-one and rating answers also carry a `confidence`.
//! The API evaluates the questions of one request in parallel, so asking thirteen questions costs
//! little more than asking one: batch everything you want to know about a state.
//!
//! # Declare what you want to know
//!
//! A struct of answers *is* the question set: each field is one question, declared with a
//! `#[jev(...)]` attribute, and the field's type is the answer it comes back as. [`Answers`]
//! derives the set, so one declaration drives both the request that goes out and the response that
//! comes back.
//!
//! ```
//! use jevlin::{Answers, ChoiceAnswer, Deserialize, NoulAnswer, ScoreAnswer};
//!
//! #[derive(Answers, Deserialize)]
//! struct Triage {
//!     #[jev(noul, "Does this convey urgency?", yes = "Time-critical", no = "No urgency")]
//!     is_urgent: NoulAnswer,
//!
//!     #[jev(choice, "Which team should handle this?",
//!           billing = "Payments, invoicing, refunds",
//!           technical = "Bugs, outages, integrations")]
//!     department: ChoiceAnswer,
//!
//!     #[jev(score, "How frustrated is the customer?", "Calm", "Frustrated", "Very angry")]
//!     frustration: ScoreAnswer,
//! }
//!
//! // The three questions travel as one request, built from the declaration…
//! let state = "Help! My payouts have been failing for 3 days.";
//! let body = serde_json::to_value(Triage::request(state)).unwrap();
//! assert_eq!(body["questions"]["is_urgent"]["type"], "noul");
//! assert_eq!(body["questions"]["is_urgent"]["criteria"]["true"], "Time-critical");
//! assert_eq!(body["questions"]["department"]["criteria"]["billing"], "Payments, invoicing, refunds");
//! assert_eq!(body["questions"]["frustration"]["criteria"][1], "Frustrated");
//!
//! // …and the answers are read back into the fields that asked for them.
//! let response: jevlin::Response = serde_json::from_str(
//!     r#"{"model":"jev-1.13.0",
//!         "answers":{
//!             "is_urgent":{"type":"noul","noul":0.95},
//!             "department":{"type":"choice","choice":"billing","probabilities":{"billing":0.88,"technical":0.12},"confidence":0.81},
//!             "frustration":{"type":"score","score":1.05,"legend":{"0":"Calm","1":"Frustrated","2":"Very angry"},"probabilities":{"0":0.0,"1":0.95,"2":0.05},"confidence":0.92}},
//!         "usage":{"input_tokens":296,"output_tokens":20}}"#,
//! )
//! .unwrap();
//!
//! let triage: Triage = response.read().unwrap();
//! assert!(triage.is_urgent >= 0.9);
//! assert_eq!(triage.department, "billing");
//! assert!(triage.frustration > 1.0);
//! assert_eq!(triage.frustration.level(2), Some("Very angry"));
//! ```
//!
//! # The `#[jev(...)]` attribute
//!
//! One attribute per field, named by the question it asks:
//!
//! |Kind|Declaration|Field type|
//! |---|---|---|
//! |[`noul`](Noul)|`#[jev(noul, instructions, yes = …, no = …)]`, both rubrics optional|[`NoulAnswer`]|
//! |[`choice`](Choice)|`#[jev(choice, instructions, option = rubric, …)]`, at least one option, at most 255|[`ChoiceAnswer`]|
//! |[`score`](Score)|`#[jev(score, instructions, level, …)]`, from 2 to 10 levels, lowest first|[`ScoreAnswer`]|
//!
//! The question's id is the field name, and the instructions, rubrics and levels are Rust
//! expressions, so they can come from anywhere — `json!` is re-exported for the structured
//! instructions that refer to fields of a structured state:
//!
//! ```
//! # use jevlin::{json, Answers, Deserialize, NoulAnswer};
//! #[derive(Answers, Deserialize)]
//! struct Review {
//!     #[jev(noul, json!({"question": "Does `verdict` contradict `reasoning`?", "verdict": "`verdict`"}))]
//!     is_consistent: NoulAnswer,
//! }
//!
//! let body = serde_json::to_value(Review::request(json!({"verdict": "approve", "reasoning": "…"}))).unwrap();
//! assert_eq!(body["model"], "jev-latest");
//! assert_eq!(body["questions"]["is_consistent"]["instructions"]["verdict"], "`verdict`");
//! ```
//!
//! Anything the API would reject is rejected at compile time instead: an unknown kind, a `choice`
//! with no options, a `score` with one level, or a field whose type does not match its question.
//!
//! # Calling the API
//!
//! With the `client` feature on (the default), `SystemOne::ask` runs the set and returns the
//! answers with what they cost; for one-off questions, `SystemOne::evaluate` takes a hand-built
//! [`Request`] and `SystemOne::ask_one` returns the [`Answer`] to a single question.
//!
//! A client opens its own HTTP connection unless one is handed to `SystemOneBuilder::client`:
//! pass one to share a connection pool between every client pointed at the same host.
//!
//! ```ignore
//! use jevlin::{Answers, Deserialize, NoulAnswer, SystemOne};
//!
//! #[derive(Answers, Deserialize)]
//! struct Triage {
//!     #[jev(noul, "Does this convey urgency?", yes = "Time-critical", no = "No urgency")]
//!     is_urgent: NoulAnswer,
//! }
//!
//! # async fn demo() -> Result<(), jevlin::Error> {
//! let client = SystemOne::new("jev-...")?;
//!
//! let outcome = client
//!     .ask::<Triage>("Help! My payouts have been failing for 3 days.")
//!     .await?;
//! if outcome.answers.is_urgent >= 0.9 {
//!     println!(
//!         "urgent, according to {} for {} input tokens",
//!         outcome.model, outcome.usage.input_tokens
//!     );
//! }
//! # Ok(())
//! # }
//! ```
//!
//! # Feature flags
//!
//! - `client` (default) — the HTTP client: `SystemOne`, `SystemOneBuilder`, `RetryConfig`, and the
//!   transport error variants. It is what a caller without a client of their own wants.
//!
//! Turn it off (`default-features = false`) and the crate is the wire contract alone — the
//! [`Question`]s, the [`Request`], the [`Response`], the [`Answers`] derive, and the errors raised
//! while building and reading them — with no HTTP stack to depend on. That is how a caller that
//! already has a client uses it: build the [`Request`], send it yourself, and read the
//! [`Response`] back.
//!
//! # Requests and responses are plain data
//!
//! [`Request`] and [`Response`] are ordinary serde types, so they can be built, stored, replayed
//! and asserted on without a network:
//!
//! ```
//! use jevlin::{Question, Request};
//!
//! let request = Request::new("Help! My payouts have been failing for 3 days.")
//!     .with_question("is_urgent", Question::noul("Does this convey urgency?"));
//!
//! let body = serde_json::to_value(&request).unwrap();
//! assert_eq!(body["model"], "jev-latest");
//! assert_eq!(body["questions"]["is_urgent"]["type"], "noul");
//!
//! let response: jevlin::Response = serde_json::from_str(
//!     r#"{"model":"jev-1.13.0",
//!         "answers":{"is_urgent":{"type":"noul","noul":0.95}},
//!         "usage":{"input_tokens":296,"output_tokens":20}}"#,
//! )
//! .unwrap();
//! assert_eq!(response.noul("is_urgent"), Some(0.95));
//! ```
//!
//! # Model aliases move
//!
//! `jev-latest` always points at the newest release, and answers can change when it moves: pin a
//! version through [`Request::with_model`] and log [`Response::model`] to see which version
//! actually answered.
//!
//! Rate limits (`429`) and overloads (`529`) are retried with exponential backoff, honoring a
//! `Retry-After` header when the API sends one; see `RetryConfig`, which needs the `client`
//! feature. Evaluations are read-only, so retrying is always safe.

#![warn(missing_docs)]

extern crate self as jevlin;

mod answer;
#[cfg(feature = "client")]
mod client;
mod error;
mod question;
mod question_set;
mod request;
#[cfg(feature = "client")]
mod retry;

pub use answer::{Answer, ChoiceAnswer, NoulAnswer, Response, ScoreAnswer, Usage};
#[cfg(feature = "client")]
pub use client::{API_KEY_ENV, SystemOne, SystemOneBuilder};
pub use error::{Error, InvalidRequest};
pub use jevlin_derive::Answers;
pub use question::{
    Choice, ChoiceCriteria, Instructions, Noul, NoulCriteria, Question, Score, ScoreCriteria,
};
pub use question_set::{Outcome, QuestionSet};
pub use request::{Model, Request, State};
/// The HTTP client `SystemOneBuilder::client` takes, re-exported so passing one costs no other
/// dependency — and so it is the same `reqwest` the client itself uses.
#[cfg(feature = "client")]
pub use reqwest::Client;
#[cfg(feature = "client")]
pub use retry::RetryConfig;

/// The derive a question set needs, re-exported from `serde`, so deriving one costs no other
/// dependency: `use jevlin::{Answers, Deserialize};` and `#[derive(Answers, Deserialize)]`.
pub use serde::Deserialize;
/// The `json!` macro, for the structured instructions and rubrics of a `#[jev(...)]` attribute.
pub use serde_json::json;
