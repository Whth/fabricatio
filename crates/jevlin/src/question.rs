//! The three question types the API understands, and the constraints each one carries.

use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::error::InvalidRequest;

/// A question's `instructions`.
///
/// A plain string holds a bare question; structured JSON holds the question in one field and the
/// data it refers to in others, so long instructions do not have to be flattened into prose. Nested
/// `state` fields and structured instruction fields are referenced by name in backticks.
pub type Instructions = Value;

/// The rubric of a [`Noul`] question: what a yes and what a no mean.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
pub struct NoulCriteria {
    /// What a yes (a value near 1) means.
    #[serde(rename = "true", skip_serializing_if = "Option::is_none")]
    pub yes: Option<Value>,
    /// What a no (a value near 0) means.
    #[serde(rename = "false", skip_serializing_if = "Option::is_none")]
    pub no: Option<Value>,
}

impl NoulCriteria {
    /// A rubric that describes neither side.
    pub fn new() -> Self {
        Self::default()
    }

    /// Describes what a yes means.
    pub fn with_yes(mut self, yes: impl Into<Value>) -> Self {
        self.yes = Some(yes.into());
        self
    }

    /// Describes what a no means.
    pub fn with_no(mut self, no: impl Into<Value>) -> Self {
        self.no = Some(no.into());
        self
    }

    /// Whether neither side is described.
    pub fn is_empty(&self) -> bool {
        self.yes.is_none() && self.no.is_none()
    }
}

/// A yes/no question.
///
/// The answer is the probability of yes, from 0 to 1.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Noul {
    /// The yes/no question to evaluate.
    pub instructions: Instructions,
    /// The optional description of what a yes and a no mean.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub criteria: Option<NoulCriteria>,
}

impl Noul {
    /// A bare yes/no question.
    pub fn new(instructions: impl Into<Instructions>) -> Self {
        Self {
            instructions: instructions.into(),
            criteria: None,
        }
    }

    /// Attaches the rubric that defines what a yes and a no mean.
    pub fn with_criteria(mut self, criteria: NoulCriteria) -> Self {
        self.criteria = Some(criteria);
        self
    }
}

/// The options of a [`Choice`] question, in name order, each mapped to the rubric that describes
/// when it applies.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
#[serde(transparent)]
pub struct ChoiceCriteria(BTreeMap<String, Value>);

impl ChoiceCriteria {
    /// No options yet.
    pub fn new() -> Self {
        Self::default()
    }

    /// Adds an option, described by the rubric that says when it applies.
    pub fn with_option(mut self, option: impl Into<String>, rubric: impl Into<Value>) -> Self {
        self.0.insert(option.into(), rubric.into());
        self
    }

    /// Adds an option that needs no extra detail.
    pub fn with_bare_option(mut self, option: impl Into<String>) -> Self {
        self.0.insert(option.into(), Value::Null);
        self
    }

    /// How many options are defined.
    pub fn len(&self) -> usize {
        self.0.len()
    }

    /// Whether no option is defined.
    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }

    /// Iterates over the options in name order.
    pub fn iter(&self) -> impl Iterator<Item = (&str, &Value)> {
        self.0
            .iter()
            .map(|(option, rubric)| (option.as_str(), rubric))
    }
}

/// A pick-one question over a set of options you define.
///
/// The answer names the highest-probability option and carries the whole probability distribution.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Choice {
    /// What the model should decide.
    pub instructions: Instructions,
    /// The options and their rubrics.
    pub criteria: ChoiceCriteria,
}

impl Choice {
    /// The most options one question may offer; the API rejects more.
    pub const MAX_OPTIONS: usize = 255;

    /// A pick-one question over `criteria`.
    ///
    /// # Errors
    /// Fails when `criteria` holds no option, or more than [`Choice::MAX_OPTIONS`] of them.
    pub fn new(
        instructions: impl Into<Instructions>,
        criteria: ChoiceCriteria,
    ) -> Result<Self, InvalidRequest> {
        if criteria.is_empty() {
            return Err(InvalidRequest::new(
                "a choice question needs at least one option",
            ));
        }
        if criteria.len() > Self::MAX_OPTIONS {
            return Err(InvalidRequest::new(format!(
                "a choice question takes at most {} options, got {}",
                Self::MAX_OPTIONS,
                criteria.len()
            )));
        }
        Ok(Self {
            instructions: instructions.into(),
            criteria,
        })
    }
}

/// The levels of a [`Score`] question, from the lowest to the highest.
#[derive(Debug, Clone, PartialEq, Default, Serialize, Deserialize)]
#[serde(transparent)]
pub struct ScoreCriteria(Vec<Value>);

impl ScoreCriteria {
    /// No levels yet.
    pub fn new() -> Self {
        Self::default()
    }

    /// Appends a level; the first appended level is level 0.
    pub fn with_level(mut self, level: impl Into<Value>) -> Self {
        self.0.push(level.into());
        self
    }

    /// How many levels are defined.
    pub fn len(&self) -> usize {
        self.0.len()
    }

    /// Whether no level is defined.
    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }

    /// Iterates over the levels in order.
    pub fn levels(&self) -> impl Iterator<Item = &Value> {
        self.0.iter()
    }
}

/// A rating question over an ordered set of levels.
///
/// The answer is a probability-weighted value across the levels, so it can land between two of them.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Score {
    /// What the model should rate.
    pub instructions: Instructions,
    /// The levels, lowest first.
    pub criteria: ScoreCriteria,
}

impl Score {
    /// The fewest levels a rating question may define; the API rejects fewer.
    pub const MIN_LEVELS: usize = 2;
    /// The most levels a rating question may define; the API rejects more.
    pub const MAX_LEVELS: usize = 10;

    /// A rating question over `criteria`.
    ///
    /// # Errors
    /// Fails unless `criteria` holds between [`Score::MIN_LEVELS`] and [`Score::MAX_LEVELS`]
    /// levels.
    pub fn new(
        instructions: impl Into<Instructions>,
        criteria: ScoreCriteria,
    ) -> Result<Self, InvalidRequest> {
        if criteria.len() < Self::MIN_LEVELS || criteria.len() > Self::MAX_LEVELS {
            return Err(InvalidRequest::new(format!(
                "a score question takes between {} and {} levels, got {}",
                Self::MIN_LEVELS,
                Self::MAX_LEVELS,
                criteria.len()
            )));
        }
        Ok(Self {
            instructions: instructions.into(),
            criteria,
        })
    }
}

/// A typed question, tagged by its `type` on the wire.
///
/// Build one through the constructors below, or through [`Noul`], [`Choice`] and [`Score`]
/// directly when the criteria deserve their own builder chain.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum Question {
    /// A yes/no question.
    Noul(Noul),
    /// A pick-one question.
    Choice(Choice),
    /// A rating question.
    Score(Score),
}

impl Question {
    /// A bare yes/no question.
    pub fn noul(instructions: impl Into<Instructions>) -> Self {
        Self::Noul(Noul::new(instructions))
    }

    /// A yes/no question with the rubric that defines what a yes and a no mean.
    pub fn noul_with_criteria(
        instructions: impl Into<Instructions>,
        criteria: NoulCriteria,
    ) -> Self {
        Self::Noul(Noul::new(instructions).with_criteria(criteria))
    }

    /// A pick-one question; see [`Choice::new`] for the constraints.
    ///
    /// # Errors
    /// Fails when the options break the API's constraints.
    pub fn choice(
        instructions: impl Into<Instructions>,
        criteria: ChoiceCriteria,
    ) -> Result<Self, InvalidRequest> {
        Ok(Self::Choice(Choice::new(instructions, criteria)?))
    }

    /// A rating question; see [`Score::new`] for the constraints.
    ///
    /// # Errors
    /// Fails when the levels break the API's constraints.
    pub fn score(
        instructions: impl Into<Instructions>,
        criteria: ScoreCriteria,
    ) -> Result<Self, InvalidRequest> {
        Ok(Self::Score(Score::new(instructions, criteria)?))
    }
}

impl From<Noul> for Question {
    fn from(question: Noul) -> Self {
        Self::Noul(question)
    }
}

impl From<Choice> for Question {
    fn from(question: Choice) -> Self {
        Self::Choice(question)
    }
}

impl From<Score> for Question {
    fn from(question: Score) -> Self {
        Self::Score(question)
    }
}
