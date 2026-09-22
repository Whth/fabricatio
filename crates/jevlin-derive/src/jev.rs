//! The `#[jev(...)]` attribute: one question, as declared on a field.

use proc_macro2::{Span, TokenStream};
use quote::quote_spanned;
use syn::parse::{Parse, ParseStream};
use syn::{Expr, Ident, LitStr, Token};

/// The kind of question a field asks.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Kind {
    /// A yes/no question, answered with a probability.
    Noul,
    /// A pick-one question.
    Choice,
    /// A rating question.
    Score,
}

impl Kind {
    /// The name as written in the attribute.
    pub(crate) fn name(self) -> &'static str {
        match self {
            Self::Noul => "noul",
            Self::Choice => "choice",
            Self::Score => "score",
        }
    }

    /// The answer type a field of this kind must have.
    pub(crate) fn answer_type(self) -> &'static str {
        match self {
            Self::Noul => "NoulAnswer",
            Self::Choice => "ChoiceAnswer",
            Self::Score => "ScoreAnswer",
        }
    }
}

/// The criteria the API accepts, as the attribute declares them.
// Variants hold a whole `syn::Expr`, and this is parsed once per field at compile time, so the size
// of a variant is irrelevant; boxing it would only add indirection to the code that reads it.
#[allow(clippy::large_enum_variant)]
pub(crate) enum Criteria {
    /// A bare question: no criteria at all.
    None,
    /// A yes/no rubric.
    Verdict {
        /// What a yes means.
        yes: Option<Expr>,
        /// What a no means.
        no: Option<Expr>,
    },
    /// An option map, in declaration order.
    Options(Vec<(String, Expr)>),
    /// An ordered list of levels.
    Levels(Vec<Expr>),
}

/// A parsed `#[jev(...)]` attribute.
pub(crate) struct JevAttribute {
    kind: Kind,
    instructions: Expr,
    criteria: Criteria,
    span: Span,
}

impl JevAttribute {
    /// The kind of question the field asks.
    pub(crate) fn kind(&self) -> Kind {
        self.kind
    }

    /// The question this field asks, as generated code.
    ///
    /// The criteria counts are checked here, and the generated tokens carry the attribute's span, so
    /// a declaration the API would reject fails the build pointing at the declaration itself.
    pub(crate) fn question(&self) -> syn::Result<TokenStream> {
        let instructions = &self.instructions;
        let span = self.span;
        match &self.criteria {
            Criteria::None => Ok(quote_spanned!(span=> ::jevlin::Question::noul(#instructions))),
            Criteria::Verdict { yes, no } => {
                let mut criteria = quote_spanned!(span=> ::jevlin::NoulCriteria::new());
                if let Some(yes) = yes {
                    criteria = quote_spanned!(span=> #criteria.with_yes(#yes));
                }
                if let Some(no) = no {
                    criteria = quote_spanned!(span=> #criteria.with_no(#no));
                }
                Ok(
                    quote_spanned!(span=> ::jevlin::Question::Noul(::jevlin::Noul {
                        instructions: ::core::convert::Into::into(#instructions),
                        criteria: ::core::option::Option::Some(#criteria),
                    })),
                )
            }
            Criteria::Options(options) => {
                reject_count(self.kind, options.len(), span)?;
                let mut criteria = quote_spanned!(span=> ::jevlin::ChoiceCriteria::new());
                for (option, rubric) in options {
                    criteria = quote_spanned!(span=> #criteria.with_option(#option, #rubric));
                }
                Ok(
                    quote_spanned!(span=> ::jevlin::Question::Choice(::jevlin::Choice {
                        instructions: ::core::convert::Into::into(#instructions),
                        criteria: #criteria,
                    })),
                )
            }
            Criteria::Levels(levels) => {
                reject_count(self.kind, levels.len(), span)?;
                let mut criteria = quote_spanned!(span=> ::jevlin::ScoreCriteria::new());
                for level in levels {
                    criteria = quote_spanned!(span=> #criteria.with_level(#level));
                }
                Ok(
                    quote_spanned!(span=> ::jevlin::Question::Score(::jevlin::Score {
                        instructions: ::core::convert::Into::into(#instructions),
                        criteria: #criteria,
                    })),
                )
            }
        }
    }
}

/// Rejects the criteria counts the API does not accept.
///
/// The bounds mirror the runtime constants in `jevlin::{Choice, Score}` (`MAX_OPTIONS`,
/// `MIN_LEVELS`, `MAX_LEVELS`), which are the API's own published limits.
fn reject_count(kind: Kind, count: usize, span: Span) -> syn::Result<()> {
    match kind {
        Kind::Noul => Ok(()),
        Kind::Choice if count == 0 => Err(syn::Error::new(
            span,
            "a `choice` question needs at least one option",
        )),
        Kind::Choice if count > 255 => Err(syn::Error::new(
            span,
            format!("a `choice` question takes at most 255 options, got {count}"),
        )),
        Kind::Choice => Ok(()),
        Kind::Score if count < 2 => Err(syn::Error::new(
            span,
            format!("a `score` question takes at least 2 levels, got {count}"),
        )),
        Kind::Score if count > 10 => Err(syn::Error::new(
            span,
            format!("a `score` question takes at most 10 levels, got {count}"),
        )),
        Kind::Score => Ok(()),
    }
}

impl Parse for JevAttribute {
    fn parse(input: ParseStream) -> syn::Result<Self> {
        let kind = input.parse::<Ident>()?;
        let span = kind.span();
        let kind = match kind.to_string().as_str() {
            "noul" => Kind::Noul,
            "choice" => Kind::Choice,
            "score" => Kind::Score,
            other => {
                return Err(syn::Error::new(
                    span,
                    format!(
                        "unknown question kind `{other}`: expected `noul`, `choice` or `score`"
                    ),
                ));
            }
        };

        if input.is_empty() {
            return Err(syn::Error::new(
                span,
                "expected the question's instructions after the kind, as in `#[jev(noul, \"Is it urgent?\")]`",
            ));
        }
        input.parse::<Token![,]>()?;
        let instructions = input.parse::<Expr>()?;

        let criteria = match kind {
            Kind::Noul => parse_verdict(input)?,
            Kind::Choice => Criteria::Options(parse_options(input)?),
            Kind::Score => Criteria::Levels(parse_levels(input)?),
        };
        Ok(Self {
            kind,
            instructions,
            criteria,
            span,
        })
    }
}

/// Parses the optional `yes = …, no = …` rubric of a `noul` question.
fn parse_verdict(input: ParseStream) -> syn::Result<Criteria> {
    let mut yes = None;
    let mut no = None;
    while !input.is_empty() {
        input.parse::<Token![,]>()?;
        if input.is_empty() {
            break;
        }
        let side = input.parse::<Ident>()?;
        input.parse::<Token![=]>()?;
        let value = input.parse::<Expr>()?;
        match side.to_string().as_str() {
            "yes" => yes = Some(value),
            "no" => no = Some(value),
            other => {
                return Err(syn::Error::new(
                    side.span(),
                    format!("unknown rubric side `{other}`: a `noul` question takes `yes` or `no`"),
                ));
            }
        }
    }
    if yes.is_none() && no.is_none() {
        Ok(Criteria::None)
    } else {
        Ok(Criteria::Verdict { yes, no })
    }
}

/// Parses the `option = "rubric"` pairs of a `choice` question.
fn parse_options(input: ParseStream) -> syn::Result<Vec<(String, Expr)>> {
    let mut options = Vec::new();
    while !input.is_empty() {
        input.parse::<Token![,]>()?;
        if input.is_empty() {
            break;
        }
        let option = if input.peek(LitStr) {
            input.parse::<LitStr>()?.value()
        } else {
            ident_name(&input.parse::<Ident>()?)
        };
        input.parse::<Token![=]>()?;
        options.push((option, input.parse::<Expr>()?));
    }
    Ok(options)
}

/// Parses the trailing level descriptions of a `score` question.
fn parse_levels(input: ParseStream) -> syn::Result<Vec<Expr>> {
    let mut levels = Vec::new();
    while !input.is_empty() {
        input.parse::<Token![,]>()?;
        if input.is_empty() {
            break;
        }
        levels.push(input.parse::<Expr>()?);
    }
    Ok(levels)
}

/// A field or option name without the raw-identifier prefix, which is how it appears on the wire.
pub(crate) fn ident_name(ident: &Ident) -> String {
    let name = ident.to_string();
    name.strip_prefix("r#").unwrap_or(&name).to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse(tokens: &str) -> syn::Result<JevAttribute> {
        syn::parse_str(tokens)
    }

    /// The question expression `tokens` generates, which is where the criteria counts are checked.
    fn question(tokens: &str) -> syn::Result<String> {
        parse(tokens)
            .and_then(|attribute| attribute.question())
            .map(|generated| generated.to_string())
    }

    /// The message of the error `tokens` is rejected with, whether parsing or generating rejects it.
    fn rejection(tokens: &str) -> String {
        match question(tokens) {
            Ok(_) => panic!("expected `{tokens}` to be rejected"),
            Err(error) => error.to_string(),
        }
    }

    #[test]
    fn parses_a_bare_question() {
        let attribute = parse("noul, \"Does this convey urgency?\"").unwrap();

        assert_eq!(attribute.kind(), Kind::Noul);
        assert!(matches!(attribute.criteria, Criteria::None));
    }

    #[test]
    fn parses_a_verdict_rubric() {
        let attribute =
            parse("noul, \"Does this convey urgency?\", yes = \"Explicit\", no = \"None\"")
                .unwrap();

        assert!(
            matches!(
                &attribute.criteria,
                Criteria::Verdict {
                    yes: Some(_),
                    no: Some(_)
                }
            ),
            "expected a rubric on both sides"
        );
    }

    #[test]
    fn parses_options_with_ident_and_string_keys() {
        let attribute =
            parse("choice, \"Which team?\", billing = \"Payments\", \"team-2\" = \"Bugs\"")
                .unwrap();

        let Criteria::Options(options) = &attribute.criteria else {
            panic!("expected options");
        };
        assert_eq!(
            options
                .iter()
                .map(|(name, _)| name.as_str())
                .collect::<Vec<_>>(),
            ["billing", "team-2"]
        );
    }

    #[test]
    fn parses_levels() {
        let attribute =
            parse("score, \"How frustrated?\", \"Calm\", \"Annoyed\", \"Furious\"").unwrap();

        let Criteria::Levels(levels) = &attribute.criteria else {
            panic!("expected levels");
        };
        assert_eq!(levels.len(), 3);
    }

    #[test]
    fn rejects_an_unknown_kind() {
        let error = rejection("binary, \"Is it so?\"");

        assert!(
            error.contains("unknown question kind `binary`"),
            "got {error}"
        );
    }

    #[test]
    fn rejects_missing_instructions() {
        let error = rejection("noul");

        assert!(
            error.contains("expected the question's instructions"),
            "got {error}"
        );
    }

    #[test]
    fn rejects_an_unknown_rubric_side() {
        let error = rejection("noul, \"Is it so?\", maybe = \"Perhaps\"");

        assert!(error.contains("unknown rubric side `maybe`"), "got {error}");
    }

    #[test]
    fn rejects_criteria_counts_the_api_would_reject() {
        let no_options = rejection("choice, \"Which team?\"");
        assert!(
            no_options.contains("at least one option"),
            "got {no_options}"
        );

        let too_many_levels = format!(
            "score, \"How frustrated?\", {}",
            (0..11)
                .map(|level| format!("\"level {level}\""))
                .collect::<Vec<_>>()
                .join(", ")
        );
        let error = rejection(&too_many_levels);
        assert!(error.contains("at most 10 levels, got 11"), "got {error}");

        let one_level = rejection("score, \"How frustrated?\", \"Calm\"");
        assert!(
            one_level.contains("at least 2 levels, got 1"),
            "got {one_level}"
        );
    }

    #[test]
    fn accepts_the_boundaries_the_api_accepts() {
        assert!(question("score, \"How frustrated?\", \"Calm\", \"Furious\"").is_ok());

        let ten_levels = format!(
            "score, \"How frustrated?\", {}",
            (0..10)
                .map(|level| format!("\"level {level}\""))
                .collect::<Vec<_>>()
                .join(", ")
        );
        assert!(question(&ten_levels).is_ok());

        let options = (0..255)
            .map(|option| format!("option_{option} = \"rubric\""))
            .collect::<Vec<_>>()
            .join(", ");
        assert!(question(&format!("choice, \"Which team?\", {options}")).is_ok());

        let too_many = (0..256)
            .map(|option| format!("option_{option} = \"rubric\""))
            .collect::<Vec<_>>()
            .join(", ");
        let error = rejection(&format!("choice, \"Which team?\", {too_many}"));
        assert!(
            error.contains("at most 255 options, got 256"),
            "got {error}"
        );
    }

    #[test]
    fn strips_the_raw_identifier_prefix() {
        assert_eq!(ident_name(&syn::parse_str("r#type").unwrap()), "type");
        assert_eq!(ident_name(&syn::parse_str("urgency").unwrap()), "urgency");
    }

    #[test]
    fn generates_a_question_expression() {
        let generated = question("noul, \"Does this convey urgency?\"").unwrap();

        assert!(generated.contains("Question :: noul"), "got {generated}");
        assert!(
            !generated.contains("ChoiceCriteria"),
            "a bare question has no criteria"
        );
    }
}
