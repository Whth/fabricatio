//! Building a request: the state, the model, and the questions filed under their ids.

use jevlin::{Model, Question, Request};

#[test]
fn defaults_to_the_latest_alias() {
    let request = Request::new("Help! My payouts have been failing for 3 days.");
    assert_eq!(request.model.as_str(), Model::LATEST_ALIAS);
    assert_eq!(request.model, Model::latest());
    assert_eq!(request.model.to_string(), "jev-latest");
}

#[test]
fn pins_a_model_on_demand() {
    let request = Request::new("state").with_model("jev-1.13.0");
    assert_eq!(request.model.as_str(), "jev-1.13.0");
}

#[test]
fn carries_state_and_questions() {
    let request = Request::new(serde_json::json!({"log": ["hi", "hello"]}))
        .with_question("is_urgent", Question::noul("Does this convey urgency?"))
        .with_question("is_urgent", Question::noul("Replaced."));
    assert_eq!(request.questions.len(), 1);
    request.validate().unwrap();
}

#[test]
fn validate_rejects_a_request_without_questions() {
    assert!(Request::new("state").validate().is_err());
}

#[test]
fn validate_rejects_a_blank_question_id() {
    let request = Request::new("state").with_question("  ", Question::noul("Does this hold?"));
    assert!(request.validate().is_err());
}
