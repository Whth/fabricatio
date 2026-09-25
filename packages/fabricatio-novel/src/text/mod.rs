//! Text primitives: the scalar-value forms every measure of this crate reads a text through.
//!
//! Chinese and English go through the same code path here — whitespace is dropped, a window is cut
//! by characters and a term by its script — so nothing below this module has to know which language
//! a run is written in. Nothing here knows about runs, scenes or scorecards either.

pub(crate) mod ngram;
mod terms;

use pyo3::prelude::*;

/// The CJK ranges the term and script measures count: Extension A, the unified block and the
/// compatibility block, the three the benchmark's term cutters have always walked.
pub(crate) fn is_cjk(c: char) -> bool {
    matches!(c, '\u{3400}'..='\u{4dbf}' | '\u{4e00}'..='\u{9fff}' | '\u{f900}'..='\u{faff}')
}

/// Whether Python's `str.split()` treats `c` as whitespace.
///
/// Rust's Unicode set misses U+001C-U+001F, Python's does not, and the Python side drops whitespace
/// from the same texts, so both have to agree on what whitespace is for their counts to agree.
pub(crate) fn is_whitespace(c: char) -> bool {
    c.is_whitespace() || matches!(c, '\u{1c}'..='\u{1f}')
}

/// The scalar values without whitespace, the form every window is cut from.
pub(crate) fn compact(text: &str) -> Vec<char> {
    compact_slice(text.chars())
}

/// The same over scalar values already read, for a measure that cuts its slice before compacting it.
pub(crate) fn compact_slice(cs: impl IntoIterator<Item = char>) -> Vec<char> {
    cs.into_iter().filter(|c| !is_whitespace(*c)).collect()
}

/// Registers the text primitives with the Python module.
///
/// The n-gram machinery below is crate-internal: the measures built on it live in
/// [`crate::benchmark`] and are registered there.
pub(crate) fn register(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    terms::register(python, m)
}

/// The first four characters of the CJK Unified Ideographs block, from U+4E00 up.
///
/// They stand in for Chinese text in tests as escapes, so no source file carries a literal in that
/// script; a test slices, chains or repeats them into whichever run it measures.
#[cfg(test)]
pub(crate) const IDEOGRAPHS: [char; 4] = ['\u{4e00}', '\u{4e8c}', '\u{4e09}', '\u{56db}'];
