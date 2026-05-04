use error_mapping::AsPyErr;
use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;
use rho_hashline::{
    apply::apply_hashline_edits,
    edit::{HashlineEdit, InsertAfterOp, ReplaceLinesOp, ReplaceOp, SetLineOp},
    format_hashlines,
};

/// Computes a hash for a single line using xxHash-based hashing.
///
/// Args:
///     line: The line content to hash.
///
/// Returns:
///     A hex string representing the line's hash.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
pub fn compute_hash(line: &str) -> String {
    rho_hashline::compute_line_hash(line).to_string()
}

/// Formats content with LINE:HASH anchors for each line.
///
/// Args:
///     content: The text content to format.
///     start_line: The starting line number (default: 1).
///
/// Returns:
///     A string where each line is prefixed with its line number and hash.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
#[pyo3(signature = (content, start_line = 1))]
pub fn format_hashes(content: &str, start_line: usize) -> String {
    format_hashlines(content, start_line)
}

/// Parses a hashline anchor in the format "LINE:HASH".
///
/// Args:
///     anchor: The anchor string to parse (e.g., "42:ab123def").
///
/// Returns:
///     A tuple of (line_number, hash_string) if valid.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
pub fn parse_hashline_anchor(anchor: &str) -> PyResult<(usize, String)> {
    rho_hashline::parse_anchor(anchor)
        .into_pyresult()
        .map(|ref_| (ref_.line, ref_.hash))
}

/// Applies a set_line edit to content based on a hashline anchor.
///
/// Args:
///     content: The original content to modify.
///     anchor: The anchor string in "LINE:HASH" format.
///     new_text: The replacement text.
///
/// Returns:
///     The modified content after applying the edit.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
pub fn apply_set_line(content: &str, anchor: &str, new_text: &str) -> PyResult<String> {
    let edits = vec![HashlineEdit::SetLine {
        set_line: SetLineOp {
            anchor: anchor.to_string(),
            new_text: new_text.to_string(),
        },
    }];
    apply_hashline_edits(content, &edits).into_pyresult()
}

/// Applies an insert_after edit to content based on a hashline anchor.
///
/// Args:
///     content: The original content to modify.
///     anchor: The anchor string in "LINE:HASH" format.
///     text: The text to insert after the anchored line.
///
/// Returns:
///     The modified content after applying the edit.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
pub fn apply_insert_after(content: &str, anchor: &str, text: &str) -> PyResult<String> {
    let edits = vec![HashlineEdit::InsertAfter {
        insert_after: InsertAfterOp {
            anchor: anchor.to_string(),
            text: text.to_string(),
        },
    }];
    apply_hashline_edits(content, &edits).into_pyresult()
}

/// Applies a replace edit (text substitution) to content.
///
/// Args:
///     content: The original content to modify.
///     old_text: The text to search for.
///     new_text: The replacement text.
///     all: Whether to replace all occurrences.
///
/// Returns:
///     The modified content after applying the edit.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
#[pyo3(signature = (content, old_text, new_text, all = false))]
pub fn apply_replace(content: &str, old_text: &str, new_text: &str, all: bool) -> PyResult<String> {
    let edits = vec![HashlineEdit::Replace {
        replace: ReplaceOp {
            old_text: old_text.to_string(),
            new_text: new_text.to_string(),
            all,
        },
    }];
    apply_hashline_edits(content, &edits).into_pyresult()
}

/// Applies a replace_lines edit to content between two anchors.
///
/// Args:
///     content: The original content to modify.
///     start_anchor: The start anchor in "LINE:HASH" format.
///     end_anchor: The end anchor in "LINE:HASH" format.
///     new_text: The replacement text for the lines range.
///
/// Returns:
///     The modified content after applying the edit.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
pub fn apply_replace_lines(
    content: &str,
    start_anchor: &str,
    end_anchor: &str,
    new_text: &str,
) -> PyResult<String> {
    let edits = vec![HashlineEdit::ReplaceLines {
        replace_lines: ReplaceLinesOp {
            start_anchor: start_anchor.to_string(),
            end_anchor: end_anchor.to_string(),
            new_text: new_text.to_string(),
        },
    }];
    apply_hashline_edits(content, &edits).into_pyresult()
}

/// Registers the hashline functions with the Python module.
///
/// Args:
///     _: The Python interpreter instance.
///     m: The Python module to register with.
///
/// Returns:
///     PyResult<()> indicating success.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compute_hash, m)?)?;
    m.add_function(wrap_pyfunction!(format_hashes, m)?)?;
    m.add_function(wrap_pyfunction!(parse_hashline_anchor, m)?)?;
    m.add_function(wrap_pyfunction!(apply_set_line, m)?)?;
    m.add_function(wrap_pyfunction!(apply_insert_after, m)?)?;
    m.add_function(wrap_pyfunction!(apply_replace, m)?)?;
    m.add_function(wrap_pyfunction!(apply_replace_lines, m)?)?;
    Ok(())
}
