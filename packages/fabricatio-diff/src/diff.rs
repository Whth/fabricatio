use pyo3::prelude::*;
use rayon::prelude::*;
use similar::{ChangeTag, TextDiff};
use strsim::normalized_damerau_levenshtein;

/// Calculates the similarity rate between two strings using the normalized Damerau-Levenshtein distance.
///
/// This function returns a float value between 0.0 and 1.0, where:
/// - 1.0 means the strings are identical
/// - 0.0 means the strings are completely different
///
/// # Arguments
///
/// - `a`: The first string to compare.
/// - `b`: The second string to compare.
///
/// # Returns
///
/// A f64 value representing the similarity rate between the two input strings.
///
/// # Example
///
/// ```
/// use fabricatio_diff::diff::rate;
///
/// let similarity = rate("hello", "helo");
/// assert!(similarity > 0.8);
/// ```
#[pyfunction]
fn rate(a: &str, b: &str) -> f64 {
    normalized_damerau_levenshtein(a, b)
}

/// Searches for a sequence of lines in `haystack` that approximately matches `needle`.
///
/// This function uses the normalized Damerau-Levenshtein distance to find a matching block
/// of lines with similarity score equal to or greater than `match_precision`.
///
/// # Arguments
///
/// - `haystack`: The full text to search within
/// - `needle`: The text pattern to find within the haystack
/// - `match_precision`: Threshold for similarity score between 0.0 and 1.0 (default: 0.9)
///
/// # Returns
///
/// An `Option<String>` containing the first matching block of lines if found,
/// or `None` if no match meets the precision threshold.
///
/// # Example
///
/// ```
/// use fabricatio_diff::diff::match_lines;
///
/// let haystack = "Hello\nWorld\nRust";
/// let needle = "W0rld";
/// let matched = match_lines(haystack, needle, Some(0.8));
/// assert!(matched.is_some());
/// ```
#[pyfunction]
#[pyo3(signature = (haystack, needle, match_precision = 0.9))]
fn match_lines(haystack: &str, needle: &str, match_precision: Option<f64>) -> Option<String> {
    // Split both inputs into lines for windowed comparison
    let haystack_lines: Vec<&str> = haystack.split('\n').collect();
    let needle_lines: Vec<&str> = needle.split('\n').collect();
    let needle_len = needle_lines.len();

    // Early return if haystack has fewer lines than needle
    if haystack_lines.len() < needle_len {
        return None;
    }

    // Parallel search through all possible line windows
    (0..=(haystack_lines.len() - needle_len))
        .into_par_iter() // Use Rayon's parallel iterator
        .find_map_any(|i| {
            // Extract window of lines with same length as needle
            let window = &haystack_lines[i..i + needle_len];
            // Convert window to single string for similarity comparison
            let window_block = window.join("\n");
            // Calculate similarity score between needle and current window
            let similarity = normalized_damerau_levenshtein(needle, &window_block);
            // Check against precision threshold (default 0.9 if not specified)
            if similarity >= match_precision.unwrap_or(0.9) {
                Some(window_block)
            } else {
                None
            }
        })
}

/// Generates a unified diff between two strings showing line-level changes.
///
/// The diff output follows unified diff format conventions where:
/// - Lines prefixed with `-` indicate deletions from `a`
/// - Lines prefixed with `+` indicate additions from `b`
/// - Unchanged lines are prefixed with a space
///
/// # Arguments
///
/// - `a`: The original/old text content
/// - `b`: The modified/new text content
///
/// # Returns
///
/// A `String` containing the diff output with each line prefixed by its change type.
///
/// # Example
///
/// ```
/// use fabricatio_diff::diff::show_diff;
///
/// let old_text = "Hello\nWorld";
/// let new_text = "Hallo\nWorld\n!";
/// let diff = show_diff(old_text, new_text);
/// assert!(diff.contains("-Hello"));
/// assert!(diff.contains("+Hallo"));
/// assert!(diff.contains("+!"));
/// ```
#[pyfunction]
fn show_diff(a: &str, b: &str) -> String {
    let diff = TextDiff::from_lines(a, b);
    let mut result = String::new();
    
    for change in diff.iter_all_changes() {
        let sign = match change.tag() {
            ChangeTag::Delete => "-",
            ChangeTag::Insert => "+",
            ChangeTag::Equal => " ",
        };
        result.push_str(&format!("{}{}", sign, change));
    }
    result
}


pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(show_diff, m)?)?;
    m.add_function(wrap_pyfunction!(rate, m)?)?;
    m.add_function(wrap_pyfunction!(match_lines, m)?)?;
    Ok(())
}
