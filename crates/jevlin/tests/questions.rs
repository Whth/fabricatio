//! The three question types: the shapes they serialize to, and the limits the API enforces.

use jevlin::{ChoiceCriteria, NoulCriteria, Question, ScoreCriteria};
use serde_json::{Value, json};

fn parse_question(json: &Value) -> Question {
    serde_json::from_value(json.clone()).unwrap()
}

fn levels(count: usize) -> ScoreCriteria {
    (0..count).fold(ScoreCriteria::new(), |criteria, level| {
        criteria.with_level(format!("level {level}"))
    })
}

fn options(count: usize) -> ChoiceCriteria {
    (0..count).fold(ChoiceCriteria::new(), |criteria, option| {
        criteria.with_bare_option(format!("option {option}"))
    })
}

#[test]
fn serializes_the_documented_shapes() {
    let noul = Question::noul_with_criteria(
        "Does this convey urgency?",
        NoulCriteria::new()
            .with_yes("Explicitly time-sensitive")
            .with_no("No urgency expressed"),
    );
    assert_eq!(
        serde_json::to_value(noul).unwrap(),
        json!({
            "type": "noul",
            "instructions": "Does this convey urgency?",
            "criteria": {"true": "Explicitly time-sensitive", "false": "No urgency expressed"}
        })
    );

    let choice = Question::choice(
        "Which team should handle this?",
        ChoiceCriteria::new()
            .with_option("billing", "Payments, invoicing, refunds")
            .with_bare_option("sales"),
    )
    .unwrap();
    assert_eq!(
        serde_json::to_value(choice).unwrap(),
        json!({
            "type": "choice",
            "instructions": "Which team should handle this?",
            "criteria": {"billing": "Payments, invoicing, refunds", "sales": null}
        })
    );

    let score = Question::score(
        "How frustrated is the customer?",
        ScoreCriteria::new()
            .with_level("Calm")
            .with_level("Frustrated")
            .with_level("Very angry"),
    )
    .unwrap();
    assert_eq!(
        serde_json::to_value(score).unwrap(),
        json!({
            "type": "score",
            "instructions": "How frustrated is the customer?",
            "criteria": ["Calm", "Frustrated", "Very angry"]
        })
    );
}

#[test]
fn a_bare_question_carries_no_criteria() {
    assert_eq!(
        serde_json::to_value(Question::noul("Does this convey urgency?")).unwrap(),
        json!({"type": "noul", "instructions": "Does this convey urgency?"})
    );
}

#[test]
fn structured_instructions_survive_the_round_trip() {
    let question = Question::noul(json!({
        "candidate": {"name": "John Smith", "location": "Oakland, California"},
        "question": "Is the resume for the same person as `candidate`?"
    }));
    assert_eq!(
        parse_question(&serde_json::to_value(&question).unwrap()),
        question
    );
}

#[test]
fn every_question_type_round_trips() {
    for question in [
        Question::noul("Does this convey urgency?"),
        Question::choice("Which team?", options(3)).unwrap(),
        Question::score("How frustrated?", levels(3)).unwrap(),
    ] {
        let encoded = serde_json::to_value(&question).unwrap();
        assert_eq!(parse_question(&encoded), question);
    }
}

#[test]
fn a_score_needs_two_to_ten_levels() {
    assert!(Question::score("How frustrated?", levels(1)).is_err());
    assert!(Question::score("How frustrated?", levels(11)).is_err());
    assert!(Question::score("How frustrated?", levels(2)).is_ok());
    assert!(Question::score("How frustrated?", levels(10)).is_ok());
}

#[test]
fn a_choice_needs_between_one_and_255_options() {
    assert!(Question::choice("Which team?", options(0)).is_err());
    assert!(Question::choice("Which team?", options(1)).is_ok());
    assert!(Question::choice("Which team?", options(255)).is_ok());
    assert!(Question::choice("Which team?", options(256)).is_err());
}

#[test]
fn a_rejected_question_explains_itself() {
    let error = Question::score("How frustrated?", levels(1)).unwrap_err();
    assert!(!error.reason().is_empty());
}
