//! The derived path end to end: the request a question set builds, and the answers read back into it.

use jevlin::{
    Answers, ChoiceAnswer, Deserialize, Error, NoulAnswer, QuestionSet, Response, ScoreAnswer,
};

/// A question set declared where its answers are read: one field per question.
#[derive(Debug, Answers, Deserialize)]
struct Triage {
    #[jev(
        noul,
        "Does this convey urgency?",
        yes = "Time-critical",
        no = "No urgency"
    )]
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

/// A narrower set over the same response, to show that answers nobody asked for are ignored.
#[derive(Debug, Answers, Deserialize)]
struct JustTheUrgency {
    #[jev(
        noul,
        "Does this convey urgency?",
        yes = "Time-critical",
        no = "No urgency"
    )]
    is_urgent: NoulAnswer,
}

const STATE: &str = "Help! My payouts have been failing for 3 days.";

/// The documented response to the three questions of [`Triage`].
fn answered() -> Response {
    serde_json::from_str(
        r#"{"model":"jev-1.13.0","answers":{
            "is_urgent":{"type":"noul","noul":0.95},
            "department":{"type":"choice","choice":"billing","probabilities":{"billing":0.88,"technical":0.12},"confidence":0.81},
            "frustration":{"type":"score","score":1.05,"legend":{"0":"Calm","1":"Frustrated","2":"Very angry"},"probabilities":{"0":0.0,"1":0.95,"2":0.05},"confidence":0.92}},
            "usage":{"input_tokens":296,"output_tokens":20}}"#,
    )
    .unwrap()
}

#[test]
fn asks_every_declared_question_in_one_request() {
    let body = serde_json::to_value(Triage::request(STATE)).unwrap();

    assert_eq!(body["state"], STATE);
    assert_eq!(body["questions"].as_object().unwrap().len(), 3);
    assert_eq!(body["questions"]["is_urgent"]["type"], "noul");
    assert_eq!(
        body["questions"]["is_urgent"]["instructions"],
        "Does this convey urgency?"
    );
    assert_eq!(
        body["questions"]["is_urgent"]["criteria"]["true"],
        "Time-critical"
    );
    assert_eq!(
        body["questions"]["is_urgent"]["criteria"]["false"],
        "No urgency"
    );
    assert_eq!(body["questions"]["department"]["type"], "choice");
    assert_eq!(
        body["questions"]["department"]["criteria"]["billing"],
        "Payments, invoicing, refunds"
    );
    assert_eq!(body["questions"]["frustration"]["type"], "score");
    assert_eq!(body["questions"]["frustration"]["criteria"][0], "Calm");
    assert_eq!(
        body["questions"]["frustration"]["criteria"][2],
        "Very angry"
    );
}

#[test]
fn the_ids_are_the_field_names_in_declaration_order() {
    assert_eq!(Triage::IDS, ["is_urgent", "department", "frustration"]);
    assert_eq!(<Triage as QuestionSet>::IDS, Triage::IDS);
}

#[test]
fn takes_the_state_as_text_or_as_structured_json() {
    let text = Triage::request(STATE);
    let structured = Triage::request(serde_json::json!({"message": STATE}));

    assert_eq!(text.state, serde_json::json!(STATE));
    assert_eq!(structured.state["message"], STATE);
    assert_eq!(text.questions, structured.questions);
}

#[test]
fn reads_the_answers_into_the_fields_that_asked_for_them() {
    let triage: Triage = answered().read().unwrap();

    assert!(triage.is_urgent >= 0.9);
    assert_eq!(triage.department, "billing");
    assert!(triage.frustration > 1.0);
    assert_eq!(triage.frustration.level(2), Some("Very angry"));
}

#[test]
fn ignores_the_answers_the_set_did_not_ask_for() {
    let urgency: JustTheUrgency = answered().read().unwrap();

    assert!(urgency.is_urgent >= 0.9);
}

#[test]
fn a_question_the_response_leaves_out_is_an_error() {
    let mut body = serde_json::to_value(answered()).unwrap();
    body["answers"]
        .as_object_mut()
        .unwrap()
        .remove("department");
    let response: Response = serde_json::from_value(body).unwrap();

    let error = response.read::<Triage>().unwrap_err();

    assert!(
        matches!(&error, Error::MissingAnswer { id } if id == "department"),
        "got {error}"
    );
}

#[test]
fn an_answer_that_does_not_fit_its_field_is_an_error() {
    // The same id, answered as a pick-one question: a yes/no field cannot hold it.
    let response: Response = serde_json::from_value(serde_json::json!({
        "model": "jev-1.13.0",
        "answers": {"is_urgent": {"type": "choice", "choice": "billing", "probabilities": {"billing": 1.0}, "confidence": 1.0}},
        "usage": {"input_tokens": 296, "output_tokens": 20}
    }))
    .unwrap();

    let error = response.read::<JustTheUrgency>().unwrap_err();

    assert!(matches!(error, Error::Decode(_)), "got {error}");
}

#[test]
fn a_serde_rename_moves_the_question_id_with_it() {
    #[derive(Debug, Answers, Deserialize)]
    struct Renamed {
        #[serde(rename = "team-2")]
        #[jev(
            choice,
            "Which team should handle this?",
            billing = "Payments, invoicing, refunds"
        )]
        team: ChoiceAnswer,
    }

    let body = serde_json::to_value(Renamed::request(STATE)).unwrap();
    assert!(body["questions"]["team-2"].is_object(), "got {body}");

    let response: Response = serde_json::from_value(serde_json::json!({
        "model": "jev-1.13.0",
        "answers": {"team-2": {"type": "choice", "choice": "billing", "probabilities": {"billing": 1.0}, "confidence": 1.0}},
        "usage": {"input_tokens": 296, "output_tokens": 20}
    }))
    .unwrap();

    assert_eq!(response.read::<Renamed>().unwrap().team, "billing");
}
