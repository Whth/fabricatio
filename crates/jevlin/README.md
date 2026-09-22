# jevlin

A typed Rust client for TypeSafe's **Jev** model, served over the System One evaluation API.

## Overview

Jev is not a chat model: it answers typed questions about a state. `jevlin` mirrors that contract
one-to-one — a request carries a `state` (text or structured JSON) together with a map of typed
questions, and the response carries one typed answer per question plus the token usage. No prompt
template to render, no boolean buried in a JSON code block to parse.

The questions are declared once, as a struct of answers, and the derive wires the request and the
response to the same fields:

```rust
use jevlin::{Answers, ChoiceAnswer, Deserialize, NoulAnswer, ScoreAnswer};

#[derive(Answers, Deserialize)]
struct Triage {
    #[jev(noul, "Does this convey urgency?", yes = "Time-critical", no = "No urgency")]
    is_urgent: NoulAnswer,

    #[jev(choice, "Which team should handle this?",
          billing = "Payments, invoicing, refunds",
          technical = "Bugs, outages, integrations")]
    department: ChoiceAnswer,

    #[jev(score, "How frustrated is the customer?", "Calm", "Frustrated", "Very angry")]
    frustration: ScoreAnswer,
}
```

The API evaluates the questions of one request in parallel, so asking thirteen things about a state
costs little more than asking one: batch what you want to know.

### Key Features

- **A question set is a struct**: `#[derive(Answers)]` turns named fields into one request, and
  fills the same fields back in from the response
- **Answers behave like the values they carry**: print them, compare them with floats and strings,
  or take the plain `f64` out of them
- **Invalid questions do not compile**: an unknown kind, a `score` with one level, a `choice` with
  no options, or a field whose type does not match its question
- **Three typed questions**: yes/no (`Noul`), pick-one (`Choice`), rating (`Score`)
- **Probabilities instead of prose**: every answer carries a probability distribution, and pick-one
  and rating answers add a `confidence`
- **The API's limits are enforced locally**: rating levels (2–10), pick-one options (≤ 255), and
  non-empty questions and ids are checked before a round trip is spent
- **Retries that follow the API's rules**: exponential backoff on `429` and `529`, honoring a
  `Retry-After` header — evaluations are read-only, so retrying is always safe
- **Plain data**: requests and responses are ordinary serde types, so they can be built, stored,
  replayed, asserted on, and cached later by a router
- **Aliases stay observable**: `jev-latest` is convenient, `Model::from("jev-1.13.0")` is
  reproducible, and every response reports the concrete model that answered

## Status

Not published to crates.io yet — consume it as a workspace path dependency. The derive lives in the
sibling crate `jevlin-derive`, which `jevlin` re-exports as `jevlin::Answers`; publishing therefore
means `jevlin-derive` first, then `jevlin`.

## Installation

```toml
[dependencies]
jevlin = { path = "../jevlin" }
```

Deriving a question set needs `serde::Deserialize` on the struct; `jevlin` re-exports it, so no
separate serde dependency is required: `use jevlin::{Answers, Deserialize};`.

## Quick Start

```rust
use jevlin::{Answers, ChoiceAnswer, Deserialize, NoulAnswer, ScoreAnswer, SystemOne};

#[derive(Answers, Deserialize)]
struct Triage {
    #[jev(noul, "Does this convey urgency?", yes = "Time-critical", no = "No urgency")]
    is_urgent: NoulAnswer,

    #[jev(choice, "Which team should handle this?",
          billing = "Payments, invoicing, refunds",
          technical = "Bugs, outages, integrations")]
    department: ChoiceAnswer,

    #[jev(score, "How frustrated is the customer?", "Calm", "Frustrated", "Very angry")]
    frustration: ScoreAnswer,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let client = SystemOne::new("jev-...")?; // or SystemOne::from_env()

    let outcome = client
        .ask::<Triage>("Help! My payouts have been failing for 3 days.")
        .await?;

    println!("urgent: {}", outcome.answers.is_urgent); // 0.95
    println!("team: {}", outcome.answers.department); // billing
    println!("frustration: {}", outcome.answers.frustration); // 1.05

    if outcome.answers.is_urgent >= 0.9 {
        println!("escalating, on {} input tokens", outcome.usage.input_tokens);
    }
    println!("answered by {}", outcome.model);

    Ok(())
}
```

## Declaring a Question Set

One field per question: the field name is the question's id, the attribute says how it is asked, and
the field's type is the answer that comes back.

| Kind | Declaration | Field type |
|---|---|---|
| `noul` | `#[jev(noul, instructions, yes = …, no = …)]` — both rubrics optional | `NoulAnswer` |
| `choice` | `#[jev(choice, instructions, option = rubric, …)]` — at least one option, at most 255 | `ChoiceAnswer` |
| `score` | `#[jev(score, instructions, level, …)]` — 2 to 10 levels, lowest first | `ScoreAnswer` |

Instructions, rubrics and levels are ordinary Rust expressions, so they can be built anywhere, and
`jevlin::json!` covers the structured instructions that refer to fields of a structured state:

```rust
use jevlin::{Answers, Deserialize, NoulAnswer, json};

#[derive(Answers, Deserialize)]
struct Review {
    #[jev(noul, json!({"question": "Does `verdict` contradict `reasoning`?", "verdict": "`verdict`"}))]
    is_consistent: NoulAnswer,
}
```

The set also reads its answers back: `Response::read::<Triage>()` files each answer under the field
that asked for it, so a stored or replayed response is as usable as a live one. Every question of the
set must be answered — a response that comes back short is an `Error::MissingAnswer`, not a struct
with a field quietly left out. Answers nobody asked for are ignored, so a narrow set can read a wide
response.

`Response::read` and `SystemOne::ask` go through serde, so answers are copied once on the way in; a
caller that reads one answer is better served by `Response::answer(id)`.

### Answers

An answer carries more than its headline value — every option's probability, the rating legend, a
`confidence` — but compares and prints like the value itself:

```rust
let triage: Triage = response.read()?;

assert!(triage.is_urgent >= 0.9);       // PartialOrd<f64>
assert_eq!(triage.department, "billing"); // PartialEq<&str>
assert!(triage.frustration > 1.0);
println!("{} {} {}", triage.is_urgent, triage.department, triage.frustration);

let score: f64 = triage.frustration.into();
assert_eq!(triage.frustration.level(2), Some("Very angry"));
assert!(triage.department.probabilities["billing"] > 0.5);
```

The richer fields stay public on `NoulAnswer`, `ChoiceAnswer` and `ScoreAnswer`, so nothing is lost
by the shorthand.

## The Three Question Types

The declaration above is a thin layer over the same three types the API takes, which stay public for
callers that build requests by hand:

| Question | Criteria | Answer |
|---|---|---|
| `Noul` — a yes/no question | optional `NoulCriteria` describing what a yes and a no mean | `noul`: the probability of yes, from 0 to 1 |
| `Choice` — pick one option | `ChoiceCriteria`, an option map of name → rubric (a bare option carries no rubric) | `choice`: the highest-probability option, plus every option's probability and a `confidence` |
| `Score` — rate along a scale | `ScoreCriteria`, an ordered list of 2–10 level descriptions | `score`: a probability-weighted value across the levels, a `legend` of the levels, and a `confidence` |

`instructions` may be a plain string, or structured JSON that holds the question in one field and the
data it refers to in others — both are accepted as-is. Anything the API would reject is rejected at
construction time instead, and the derive rejects it at compile time:

```rust
use jevlin::{Question, ScoreCriteria};

let rating = Question::score(
    "How frustrated is the author?",
    ScoreCriteria::new()
        .with_level("Calm")
        .with_level("Annoyed")
        .with_level("Furious"),
)?;

// Eleven levels, or one, is an error before anything is sent.
assert!(Question::score("How frustrated?", ScoreCriteria::new().with_level("Calm")).is_err());
```

## Calling the API

### A question set

```rust
let outcome = client.ask::<Triage>("The build failed twice with the same linker error.").await?;
```

The `Outcome` carries `answers`, the `model` that answered, and the `usage` of the call.

### One question at a time

```rust
use jevlin::{Answer, Question};

let answer = client
    .ask_one(
        "The build failed twice with the same linker error.",
        Question::noul("Does this need attention right now?"),
    )
    .await?;

match answer {
    Answer::Noul(noul) => println!("{noul}"),
    Answer::Choice(choice) => println!("{choice}"),
    Answer::Score(score) => println!("{score}"),
}
```

### A request by hand

```rust
use jevlin::{ChoiceCriteria, Question, Request};

let request = Request::new("Help! My payouts have been failing for 3 days.")
    .with_question("is_urgent", Question::noul("Does this convey urgency?"))
    .with_question(
        "department",
        Question::choice(
            "Which team should handle this?",
            ChoiceCriteria::new()
                .with_option("billing", "Payments, invoicing, refunds")
                .with_option("technical", "Bugs, outages, integrations"),
        )?,
    );

let response = client.evaluate(&request).await?;
println!("urgent: {:?}", response.noul("is_urgent"));
println!("team: {:?}", response.choice("department"));

let triage: Triage = response.read()?;
```

`Request` and `Response` are plain serde types, so a hand-built request can be stored, replayed, or
asserted on without a network, and a typed set reads the response of either path.

### Pinning a model

`jev-latest` follows TypeSafe's releases, and answers can change when it moves. Pin a version for
reproducible runs, and log the model on the response to see which one actually answered:

```rust
let request = Triage::request(state).with_model("jev-1.13.0");
let response = client.evaluate(&request).await?;
println!("answered by {}", response.model);
```

### Timeouts, retries, and other hosts

```rust
use std::time::Duration;

use jevlin::{RetryConfig, SystemOne};

let client = SystemOne::builder("jev-...")
    .base_url("https://api.typesafe.ai")
    .timeout(Duration::from_secs(30))
    .retry(RetryConfig {
        max_attempts: 6,
        initial_backoff: Duration::from_millis(250),
        max_backoff: Duration::from_secs(10),
        backoff_multiplier: 2,
    })
    .build()?;
```

The default policy is four attempts, backing off 500 ms, 1 s, 2 s, capped at 8 s — used only when the
API sends no numeric `Retry-After`.

### API keys

The key is held in a [`secrecy::SecretString`](https://docs.rs/secrecy), so it never shows up in
`Debug` output, and it is exposed only when the `Authorization` header is built.
`SystemOne::from_env()` reads `JEVLIN_API_KEY`.

## Errors

`Error` distinguishes what a caller can actually act on:

| Variant | Raised when |
|---|---|
| `Invalid` | the request breaks the API's constraints — caught locally, never sent |
| `MissingApiKey` | `from_env()` found no `JEVLIN_API_KEY` |
| `InvalidBaseUrl` | the configured base URL is not a URL |
| `Unauthorized` | the API answered `401` |
| `Unprocessable` | the API answered `422`; the detail names the offending field |
| `RateLimited` / `Overloaded` | the API answered `429` / `529`, with the delay it asked for |
| `Unexpected` | any other status |
| `MissingAnswer` | the response left a question of the set unanswered |
| `Transport` / `Decode` | the HTTP layer failed, or a body did not match the documented shape |

`Error::is_retryable()` reports whether another attempt could succeed, and `Error::retry_after()`
returns the delay the API asked for.

## Testing

```bash
cargo test -p jevlin -p jevlin-derive   # integration and doc tests for both crates
JEVLIN_API_KEY=... cargo test -p jevlin -- --ignored   # one live round trip (bash)
```

```powershell
$env:JEVLIN_API_KEY = "jev-..."; cargo test -p jevlin -- --ignored
```

The tests live in `crates/jevlin/tests/`, one file per area: `client.rs` for everything the client
does over HTTP, `questions.rs`, `requests.rs`, `answers.rs` and `retry.rs` for the pieces it is built
from, and `answers_derive.rs` for the derive end to end. `tests/support/` holds the fake System One
server — a real loopback HTTP server, so the request line, the auth header, the JSON body, the status
mapping, `Retry-After`, and the timeout are all exercised through the actual HTTP stack, and the
error taxonomy is asserted on the errors a caller really gets. The derive crate's own tests cover the
attribute grammar and every declaration it rejects; they stay unit tests because a proc-macro crate
cannot export the parser it tests.

## Benchmarks

```bash
cargo bench -p jevlin
```

The benchmark measures what the client adds to a call — building a typed request, serializing the
body (three questions, and a batch of thirteen), parsing a response, and reading it into a question
set — so the numbers are the library's cost rather than the network's.

```bash
JEVLIN_LIVE_BENCH=1 JEVLIN_API_KEY=... cargo bench -p jevlin -- live
```

The live group measures the API's own latency for 1, 4, and 13 questions, which is what batching
buys: thirteen questions are one round trip, not thirteen. It is off by default because every sample
is a call the caller pays for.

## License

Licensed under the terms of the repository's `LICENSE` file, which the workspace `license-file`
setting points at.
