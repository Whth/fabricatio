//! The response: one typed answer per question, plus the token usage.

use std::cmp::Ordering;
use std::collections::BTreeMap;
use std::fmt::{self, Display, Formatter};

use serde::{Deserialize, Serialize};

use crate::error::Error;
use crate::question_set::QuestionSet;
use crate::request::Model;

/// The tokens a request consumed.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Usage {
    /// Tokens the model read, across the state and every question.
    pub input_tokens: u64,
    /// Tokens the model wrote. TypeSafe does not bill for these.
    pub output_tokens: u64,
}

/// The answer to a [`Noul`](crate::Noul) question.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct NoulAnswer {
    /// The yes/no answer, from 0 (no) to 1 (yes).
    pub noul: f64,
}

impl Display for NoulAnswer {
    /// The probability of yes, to two decimals.
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        write!(formatter, "{:.2}", self.noul)
    }
}

impl From<NoulAnswer> for f64 {
    fn from(answer: NoulAnswer) -> Self {
        answer.noul
    }
}

impl PartialEq<f64> for NoulAnswer {
    fn eq(&self, other: &f64) -> bool {
        self.noul == *other
    }
}

impl PartialOrd<f64> for NoulAnswer {
    fn partial_cmp(&self, other: &f64) -> Option<Ordering> {
        self.noul.partial_cmp(other)
    }
}

/// The answer to a [`Choice`](crate::Choice) question.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ChoiceAnswer {
    /// The highest-probability option.
    pub choice: String,
    /// Every option, mapped to its probability.
    pub probabilities: BTreeMap<String, f64>,
    /// How certain the model is, derived from the probabilities.
    pub confidence: f64,
}

impl Display for ChoiceAnswer {
    /// The chosen option.
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str(&self.choice)
    }
}

impl PartialEq<&str> for ChoiceAnswer {
    fn eq(&self, other: &&str) -> bool {
        self.choice == *other
    }
}

impl PartialEq<str> for ChoiceAnswer {
    fn eq(&self, other: &str) -> bool {
        self.choice == other
    }
}

/// The answer to a [`Score`](crate::Score) question.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ScoreAnswer {
    /// The probability-weighted rating across the levels.
    pub score: f64,
    /// Each level number, mapped back to the level description from the question.
    pub legend: BTreeMap<String, String>,
    /// Each level, mapped to its probability.
    pub probabilities: BTreeMap<String, f64>,
    /// How certain the model is, derived from the probabilities.
    pub confidence: f64,
}

impl ScoreAnswer {
    /// The description of the level at `index`, as given in the question's criteria.
    pub fn level(&self, index: usize) -> Option<&str> {
        self.legend.get(&index.to_string()).map(String::as_str)
    }
}

impl Display for ScoreAnswer {
    /// The probability-weighted rating, to two decimals.
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        write!(formatter, "{:.2}", self.score)
    }
}

impl From<ScoreAnswer> for f64 {
    fn from(answer: ScoreAnswer) -> Self {
        answer.score
    }
}

impl PartialEq<f64> for ScoreAnswer {
    fn eq(&self, other: &f64) -> bool {
        self.score == *other
    }
}

impl PartialOrd<f64> for ScoreAnswer {
    fn partial_cmp(&self, other: &f64) -> Option<Ordering> {
        self.score.partial_cmp(other)
    }
}

/// One answer, tagged by its `type` and matching the question it answers.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum Answer {
    /// The answer to a yes/no question.
    Noul(NoulAnswer),
    /// The answer to a pick-one question.
    Choice(ChoiceAnswer),
    /// The answer to a rating question.
    Score(ScoreAnswer),
}

impl Answer {
    /// This answer as a yes/no answer, when that is what it is.
    pub fn as_noul(&self) -> Option<&NoulAnswer> {
        if let Self::Noul(answer) = self {
            Some(answer)
        } else {
            None
        }
    }

    /// This answer as a pick-one answer, when that is what it is.
    pub fn as_choice(&self) -> Option<&ChoiceAnswer> {
        if let Self::Choice(answer) = self {
            Some(answer)
        } else {
            None
        }
    }

    /// This answer as a rating answer, when that is what it is.
    pub fn as_score(&self) -> Option<&ScoreAnswer> {
        if let Self::Score(answer) = self {
            Some(answer)
        } else {
            None
        }
    }

    /// How certain the model is, for the answer types that carry a confidence.
    ///
    /// A yes/no answer has none: its probability is the answer.
    pub fn confidence(&self) -> Option<f64> {
        match self {
            Self::Noul(_) => None,
            Self::Choice(answer) => Some(answer.confidence),
            Self::Score(answer) => Some(answer.confidence),
        }
    }
}

/// A System One response: the answers, filed under the ids you chose, plus the usage.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Response {
    /// The model that performed the evaluation — the concrete version, not the alias requested.
    pub model: Model,
    /// One answer per question, under the same ids.
    pub answers: BTreeMap<String, Answer>,
    /// The tokens the request consumed.
    pub usage: Usage,
}

impl Response {
    /// The answer filed under `id`.
    pub fn answer(&self, id: &str) -> Option<&Answer> {
        self.answers.get(id)
    }

    /// The probability of yes for the question filed under `id`, when it is a yes/no question.
    pub fn noul(&self, id: &str) -> Option<f64> {
        self.answer(id)?.as_noul().map(|answer| answer.noul)
    }

    /// The chosen option for the question filed under `id`, when it is a pick-one question.
    pub fn choice(&self, id: &str) -> Option<&str> {
        self.answer(id)?
            .as_choice()
            .map(|answer| answer.choice.as_str())
    }

    /// The probability-weighted rating for the question filed under `id`, when it is a rating
    /// question.
    pub fn score(&self, id: &str) -> Option<f64> {
        self.answer(id)?.as_score().map(|answer| answer.score)
    }

    /// Reads the answers to `T` out of this response.
    ///
    /// This is the typed counterpart of [`Response::answer`]: every question of `T` is filed into
    /// the field that asked it, through serde. Answers `T` did not ask for are ignored, and a
    /// question this response leaves unanswered is an error rather than a field left out.
    ///
    /// Reading goes through serde's data model, so it copies the answers once; a caller that reads
    /// a single answer is better served by [`Response::answer`].
    ///
    /// # Errors
    /// [`Error::MissingAnswer`], naming the first question of `T` this response does not answer,
    /// and [`Error::Decode`] when an answer does not fit the field that asked for it.
    pub fn read<T: QuestionSet>(&self) -> Result<T, Error> {
        for id in T::IDS {
            if !self.answers.contains_key(*id) {
                return Err(Error::MissingAnswer {
                    id: (*id).to_string(),
                });
            }
        }
        Ok(serde_json::from_value(serde_json::to_value(
            &self.answers,
        )?)?)
    }
}
