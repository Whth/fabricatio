// benches/client.rs
//!
//! What one call costs the client itself: the request it builds, the body it sends, and the answers
//! it reads back. The round trip is the API's cost, so the `live` group measures it off by default —
//! it needs `JEVLIN_API_KEY` plus `JEVLIN_LIVE_BENCH=1`, and it spends API calls.

use std::hint::black_box;
use std::time::Duration;

use criterion::{Bencher, Criterion, criterion_group, criterion_main};
use jevlin::{
    Answers, ChoiceAnswer, Deserialize, NoulAnswer, Question, Request, Response, ScoreAnswer,
    SystemOne,
};

const STATE: &str = "Help! My payouts have been failing for 3 days.";

/// The documented question set, declared the way a caller declares one.
#[derive(Answers, Deserialize)]
struct Triage {
    #[jev(noul, "Does this convey urgency?")]
    is_urgent: NoulAnswer,
    #[jev(
        choice,
        "Which team should handle this?",
        billing = "Payments, invoicing, refunds",
        technical = "Bugs, outages, integrations"
    )]
    department: ChoiceAnswer,
    #[jev(
        score,
        "How frustrated is the customer?",
        "Calm",
        "Frustrated",
        "Very angry"
    )]
    frustration: ScoreAnswer,
}

const RESPONSE: &str = r#"{"model":"jev-1.13.0","answers":{
    "is_urgent":{"type":"noul","noul":0.95},
    "department":{"type":"choice","choice":"billing","probabilities":{"billing":0.88,"technical":0.12},"confidence":0.81},
    "frustration":{"type":"score","score":1.05,"legend":{"0":"Calm","1":"Frustrated","2":"Very angry"},"probabilities":{"0":0.0,"1":0.95,"2":0.05},"confidence":0.92}},
    "usage":{"input_tokens":296,"output_tokens":20}}"#;

fn response() -> Response {
    serde_json::from_str(RESPONSE).unwrap()
}

/// A request with `questions` yes/no questions, the way the API is meant to be used: batched.
fn batched(questions: usize) -> Request {
    (0..questions).fold(Request::new(STATE), |request, index| {
        request.with_question(
            format!("question_{index}"),
            Question::noul(format!("Question {index}?")),
        )
    })
}

fn builds_the_request(b: &mut Bencher) {
    b.iter(|| black_box(Triage::request(black_box(STATE))));
}

fn serializes_the_request(b: &mut Bencher) {
    let request = Triage::request(STATE);
    b.iter(|| black_box(serde_json::to_vec(black_box(&request)).unwrap()));
}

fn serializes_a_batch(b: &mut Bencher) {
    let request = batched(13);
    b.iter(|| black_box(serde_json::to_vec(black_box(&request)).unwrap()));
}

fn parses_the_response(b: &mut Bencher) {
    b.iter(|| black_box(serde_json::from_str::<Response>(black_box(RESPONSE)).unwrap()));
}

/// Reads a response into the set, and uses the answers the way a caller does.
fn reads_the_answers(b: &mut Bencher) {
    let response = response();
    b.iter(|| {
        let triage = response.read::<Triage>().unwrap();
        black_box(triage.is_urgent >= 0.9);
        black_box(triage.department == "billing");
        black_box(triage.frustration > 1.0);
    });
}

fn looks_the_answers_up_by_id(b: &mut Bencher) {
    let response = response();
    b.iter(|| {
        black_box(response.noul(black_box("is_urgent")));
        black_box(response.choice(black_box("department")));
        black_box(response.score(black_box("frustration")));
    });
}

fn client_benchmark(c: &mut Criterion) {
    c.bench_function("request/build", builds_the_request);
    c.bench_function("request/serialize", serializes_the_request);
    c.bench_function("request/serialize 13 questions", serializes_a_batch);
    c.bench_function("response/parse", parses_the_response);
    c.bench_function("response/read into a question set", reads_the_answers);
    c.bench_function("response/look up by id", looks_the_answers_up_by_id);
}

/// The API's latency by question count, which is what batching buys: thirteen questions are one
/// round trip, not thirteen.
fn live_benchmark(c: &mut Criterion) {
    if std::env::var("JEVLIN_LIVE_BENCH").as_deref() != Ok("1") {
        eprintln!("set JEVLIN_LIVE_BENCH=1 to benchmark against the live API");
        return;
    }
    let Ok(client) = SystemOne::from_env() else {
        eprintln!("JEVLIN_API_KEY is unset: skipping the live benchmark");
        return;
    };
    let runtime = tokio::runtime::Runtime::new().unwrap();
    let mut group = c.benchmark_group("live");
    group.sample_size(10);
    group.measurement_time(Duration::from_secs(30));
    for questions in [1, 4, 13] {
        let request = batched(questions);
        group.bench_function(format!("{questions} questions"), |b| {
            b.iter(|| {
                black_box(
                    runtime
                        .block_on(client.evaluate(black_box(&request)))
                        .unwrap(),
                )
            });
        });
    }
    group.finish();
}

criterion_group!(benches, client_benchmark, live_benchmark);
criterion_main!(benches);
