//! Reading a response: the documented shapes, the typed accessors, and how answers behave.

use jevlin::{Response, Usage};
use serde_json::json;

fn documented_response() -> Response {
    serde_json::from_value(json!({
        "model": "jev-1.13.0",
        "answers": {
            "is_urgent": {"type": "noul", "noul": 0.95},
            "department": {
                "type": "choice",
                "choice": "billing",
                "probabilities": {"billing": 0.88, "technical": 0.12, "sales": 0.0},
                "confidence": 0.81
            },
            "frustration": {
                "type": "score",
                "score": 1.05,
                "legend": {"0": "Calm", "1": "Frustrated", "2": "Very angry"},
                "probabilities": {"0": 0.0, "1": 0.95, "2": 0.05},
                "confidence": 0.92
            }
        },
        "usage": {"input_tokens": 296, "output_tokens": 20}
    }))
    .unwrap()
}

#[test]
fn parses_the_documented_answers() {
    let response = documented_response();

    assert_eq!(response.model.as_str(), "jev-1.13.0");
    assert_eq!(
        response.usage,
        Usage {
            input_tokens: 296,
            output_tokens: 20
        }
    );
    assert_eq!(response.noul("is_urgent"), Some(0.95));
    assert_eq!(response.choice("department"), Some("billing"));
    assert_eq!(response.score("frustration"), Some(1.05));
    assert_eq!(response.answer("unasked"), None);
}

#[test]
fn typed_accessors_stay_on_their_own_answer_type() {
    let response = documented_response();

    assert!(response.noul("department").is_none());
    assert!(response.choice("is_urgent").is_none());
    assert!(response.score("is_urgent").is_none());
    assert_eq!(
        response.answer("is_urgent").unwrap().as_choice(),
        None,
        "a noul answer is not a choice answer"
    );
}

#[test]
fn confidence_belongs_to_choice_and_score_answers_only() {
    let response = documented_response();

    assert_eq!(response.answer("is_urgent").unwrap().confidence(), None);
    assert_eq!(
        response.answer("department").unwrap().confidence(),
        Some(0.81)
    );

    let score = response.answer("frustration").unwrap();
    assert_eq!(score.confidence(), Some(0.92));
    assert_eq!(score.as_score().unwrap().level(2), Some("Very angry"));
    assert_eq!(score.as_score().unwrap().level(7), None);
}

#[test]
fn answers_print_and_compare_like_the_values_they_carry() {
    let response = documented_response();

    let urgency = response.answer("is_urgent").unwrap().as_noul().unwrap();
    assert!(*urgency >= 0.95);
    assert!(*urgency > 0.9);
    assert_eq!(urgency.to_string(), "0.95");
    assert_eq!(f64::from(urgency.clone()), 0.95);

    let department = response.answer("department").unwrap().as_choice().unwrap();
    assert_eq!(department, "billing");
    assert_ne!(department, "sales");
    assert_eq!(department.to_string(), "billing");

    let frustration = response.answer("frustration").unwrap().as_score().unwrap();
    assert!(*frustration > 1.0);
    assert!(*frustration < 1.1);
    assert_eq!(frustration.to_string(), "1.05");
    assert_eq!(f64::from(frustration.clone()), 1.05);
}
