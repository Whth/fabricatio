//! Question sets: a struct of answers, and what the call that filled it in cost.

use serde::de::DeserializeOwned;

use crate::answer::Usage;
use crate::request::{Model, Request, State};

/// Questions asked about one state, and the answers to them.
///
/// Derive it with [`Answers`](crate::Answers) instead of implementing it by hand: the derive builds
/// the request from the `#[jev(...)]` attributes on the fields, and
/// [`Response::read`](crate::Response::read) fills the same fields in from the response.
pub trait QuestionSet: DeserializeOwned {
    /// The question ids this set asks, in declaration order.
    const IDS: &'static [&'static str];

    /// Builds the request that asks all of them about `state`.
    fn request(state: State) -> Request;
}

/// The answers to a [`QuestionSet`], with the model that answered them and what they cost.
#[derive(Debug, Clone, PartialEq)]
pub struct Outcome<T> {
    /// The answers, one field per question.
    pub answers: T,
    /// The model that performed the evaluation — the concrete version, not the alias requested.
    pub model: Model,
    /// The tokens the request consumed.
    pub usage: Usage,
}
