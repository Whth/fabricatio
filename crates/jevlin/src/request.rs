//! The request: one state, one model, and a map of named questions.

use std::collections::BTreeMap;
use std::fmt::{Display, Formatter};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::error::InvalidRequest;
use crate::question::Question;

/// The `state`: the content to evaluate.
///
/// A state is the material a judgement is made about: a support message, a passage of text, or the
/// current state of your application. It is text only — a string, a JSON object, or an array of
/// text — so images, audio, and video are out of scope.
///
/// An object suits most requests, because every part of the state gets a name and its relations
/// stay clear; a string suits a case that turns on one piece of text, and an array a sequence of
/// messages or records. Questions may point at named fields in backticks, nested ones included.
pub type State = Value;

/// The model that handles a request.
///
/// Jev's primary training language is English; other languages, CJK scripts included, are accepted
/// but answer with lower accuracy.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(transparent)]
pub struct Model(String);

impl Model {
    /// The alias that always points at the newest release.
    ///
    /// It moves when TypeSafe ships a model, and answers can change with it: pin a version with
    /// `Model::from("jev-1.13.0")` for reproducible runs, and log the [`Model`] on the
    /// [`Response`](crate::Response) to see which version actually answered.
    pub const LATEST_ALIAS: &'static str = "jev-latest";

    /// The moving `jev-latest` alias.
    pub fn latest() -> Self {
        Self(Self::LATEST_ALIAS.to_string())
    }

    /// The model id, as sent on the wire.
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl From<&str> for Model {
    fn from(model: &str) -> Self {
        Self(model.to_string())
    }
}

impl From<String> for Model {
    fn from(model: String) -> Self {
        Self(model)
    }
}

impl Display for Model {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(&self.0)
    }
}

/// A System One request: one `state`, one `model`, and one entry per question.
///
/// Every question sees the same state and is evaluated independently of the others, so a request
/// may mix the three question types freely, and a question added later does not disturb the ones
/// beside it.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Request {
    /// The one state every question of this request is asked about.
    pub state: State,
    /// The model that handles the request; defaults to the moving [`Model::LATEST_ALIAS`].
    pub model: Model,
    /// The questions, each filed under an id you choose. Ids are not sent to the model and are not
    /// used in inference; the answers come back under the same ids.
    pub questions: BTreeMap<String, Question>,
}

impl Request {
    /// A request that evaluates `state` with the `jev-latest` model and no questions yet.
    pub fn new(state: impl Into<State>) -> Self {
        Self {
            state: state.into(),
            model: Model::latest(),
            questions: BTreeMap::new(),
        }
    }

    /// Pins the model instead of the moving `jev-latest` alias.
    pub fn with_model(mut self, model: impl Into<Model>) -> Self {
        self.model = model.into();
        self
    }

    /// Adds a question under `id`, replacing a question already filed under it.
    pub fn with_question(mut self, id: impl Into<String>, question: impl Into<Question>) -> Self {
        self.questions.insert(id.into(), question.into());
        self
    }

    /// Checks the constraints the API enforces on the request body.
    ///
    /// [`SystemOne::evaluate`](crate::SystemOne::evaluate) calls this before sending, so an empty
    /// request fails locally instead of costing a round trip.
    ///
    /// # Errors
    /// Fails when the request holds no question, or a question whose id is blank.
    pub fn validate(&self) -> Result<(), InvalidRequest> {
        if self.questions.is_empty() {
            return Err(InvalidRequest::new("a request needs at least one question"));
        }
        if self.questions.keys().any(|id| id.trim().is_empty()) {
            return Err(InvalidRequest::new("a question id must not be blank"));
        }
        Ok(())
    }
}
