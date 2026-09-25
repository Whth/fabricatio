//! The distinctive terms a text uses.

use std::borrow::Cow;

use pyo3::prelude::*;
use pyo3::types::PySet;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

use super::is_cjk;

/// The lengths a CJK run is cut at: CJK has no word boundaries, so terms are cut at the sizes that
/// carry most short phrases.
const TERM_SIZES: [usize; 2] = [3, 4];

/// The shortest Latin word that carries a term; shorter ones are function words in practice.
const WORD_MIN_CHARS: usize = 4;

/// Whether Python's `[0-9A-Za-z_]+` holds a scalar value.
fn is_word(c: char) -> bool {
    c.is_ascii_alphanumeric() || c == '_'
}

/// Every `size`-character window of a CJK run, borrowed from the run itself.
///
/// Two cursors over the run's scalars do the cutting: one at the window's first character, one
/// `size` characters ahead at its last. Pairing them is what keeps the cut free of re-encoding —
/// each window is a slice of the prose, not a rebuilt string — and the cursor that runs out ends
/// the windows, so a run shorter than `size` yields none.
fn cjk_terms<'a>(run: &'a str, size: usize) -> impl Iterator<Item = &'a str> + 'a {
    let starts = run.char_indices().map(|(index, _)| index);
    let ends = starts.clone().chain([run.len()]).skip(size);
    starts.zip(ends).map(move |(start, end)| &run[start..end])
}

/// Every term of the text: CJK runs cut at 3 and 4 characters, then Latin words of 4+ characters.
///
/// Terms are borrowed from the text wherever they can be; only a Latin word carrying uppercase
/// letters is allocated, because its term is the lowercase form.
///
/// Ordinary prose vocabulary is not filtered out on purpose: the term sets are only ever compared
/// against other term sets of the same run, where the plan text supplies the licence for every word
/// it uses itself.
fn terms_of(text: &str) -> impl Iterator<Item = Cow<'_, str>> {
    let cjk = text
        .split(|scalar: char| !is_cjk(scalar))
        .filter(|run| !run.is_empty())
        .flat_map(|run| {
            TERM_SIZES
                .into_iter()
                .flat_map(move |size| cjk_terms(run, size))
        })
        .map(Cow::Borrowed);
    let words = text
        .split(|scalar: char| !is_word(scalar))
        .filter(|word| word.len() >= WORD_MIN_CHARS)
        .map(|word| {
            if word.bytes().any(|byte| byte.is_ascii_uppercase()) {
                Cow::Owned(word.to_ascii_lowercase())
            } else {
                Cow::Borrowed(word)
            }
        });
    cjk.chain(words)
}

/// The distinctive terms of the text: every CJK 3..4-char n-gram and Latin words of 4+ chars, lowercased.
///
/// The set is built straight into its Python form: the terms are inserted as they are cut, so no
/// copy of the text's vocabulary is hashed twice and no term is allocated twice.
///
/// Args:
///     text: The text to read the terms of.
///
/// Returns:
///     The set of terms.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[cfg_attr(
    feature = "stubgen",
    gen_stub(override_return_type(
        type_repr = "builtins.set[builtins.str]",
        imports = ("builtins",)
    ))
)]
#[pyfunction]
fn significant_terms<'py>(py: Python<'py>, text: &str) -> PyResult<Bound<'py, PySet>> {
    let terms = PySet::empty(py)?;
    for term in terms_of(text) {
        terms.add(term.as_ref())?;
    }
    Ok(terms)
}

/// Registers the term surface with the Python module.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(significant_terms, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::collections::HashSet;

    use super::*;
    use crate::text::IDEOGRAPHS;

    /// The terms of the text, as the sequence the iterator reads them in.
    fn terms(text: &str) -> HashSet<String> {
        terms_of(text).map(Cow::into_owned).collect()
    }

    #[test]
    fn reads_cjk_runs_at_three_and_four_characters() {
        let run: Vec<char> = IDEOGRAPHS.to_vec();
        let mut expected: HashSet<String> = HashSet::new();
        for size in TERM_SIZES {
            for start in 0..=run.len() - size {
                expected.insert(run[start..start + size].iter().collect());
            }
        }
        let text: String = run.iter().collect();
        assert_eq!(terms(&text), expected);

        // A run of four holds two 3-grams and the 4-gram itself; a run of two holds none, and the
        // three-character Latin word between them is not a term either.
        assert_eq!(
            terms(&format!(
                "{} abc {}",
                text,
                run[..2].iter().collect::<String>()
            )),
            HashSet::from([
                run[..3].iter().collect::<String>(),
                run[1..].iter().collect::<String>(),
                text,
            ])
        );
    }

    #[test]
    fn reads_latin_words_from_four_characters() {
        assert_eq!(
            terms("the quick brown fox jumps_2 THE_THE"),
            HashSet::from([
                "quick".to_string(),
                "brown".to_string(),
                "jumps_2".to_string(),
                "the_the".to_string(),
            ])
        );
        assert!(terms("fox abc the").is_empty());
        assert_eq!(terms("12345"), HashSet::from(["12345".to_string()]));
    }

    #[test]
    fn reads_nothing_out_of_a_text_without_terms() {
        assert!(terms("").is_empty());
        assert!(terms(" \n\t ,;.! ").is_empty());
    }

    #[test]
    fn borrows_every_term_the_text_already_holds() {
        let text = format!("the quick brown {}", IDEOGRAPHS.iter().collect::<String>());
        assert!(
            terms_of(&text).all(|term| matches!(term, Cow::Borrowed(_))),
            "a text without uppercase reads borrows"
        );
        assert!(
            terms_of("The Quick").any(|term| matches!(term, Cow::Owned(word) if word == "quick")),
            "a word carrying uppercase reads its lowercase form"
        );
    }

    #[test]
    fn cuts_a_run_shorter_than_the_window_into_nothing() {
        let short: String = IDEOGRAPHS[..2].iter().collect();
        let exactly: String = IDEOGRAPHS[..3].iter().collect();
        assert_eq!(terms(&short), HashSet::new());
        assert_eq!(terms(&exactly), HashSet::from([exactly]));
    }
}
