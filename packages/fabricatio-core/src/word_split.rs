use pyo3::prelude::*;
use unicode_segmentation::UnicodeSegmentation;

/// split the string into words
#[pyfunction]
fn split_word_bounds(string: &str) -> Vec<String> {
    string.split_word_bounds().map(|s| s.to_string()).collect()
}

/// split the string into sentences
#[pyfunction]
fn split_sentence_bounds(string: &str) -> Vec<String> {
    string
        .split_sentence_bounds()
        .map(|s| s.to_string())
        .collect()
}

/// Splits a given string into chunks based on the specified maximum chunk size and overlapping rate.
///
/// The function prioritizes splitting at sentence boundaries. If a sentence exceeds the maximum chunk size,
/// it will be split into smaller parts. The overlapping rate determines how much overlap there should be
/// between consecutive chunks.
///
/// # Parameters
/// - `string`: The input string to be split.
/// - `max_chunk_size`: The maximum number of words allowed in a chunk.
/// - `max_overlapping_rate`: The rate of overlapping between consecutive chunks, expressed as a fraction of the chunk size.
///
/// # Returns
/// A vector of strings, where each string is a chunk of the original input.
#[pyfunction]
#[pyo3(signature = (string, max_chunk_size, max_overlapping_rate=0.3))]
fn split_into_chunks(
    string: &str,
    max_chunk_size: usize,
    max_overlapping_rate: f64,
) -> Vec<String> {
    let sentences = split_sentence_bounds(string);
    let mut res = vec![];
    let max_overlapping_size = (max_overlapping_rate * max_chunk_size as f64) as usize;
    let mut overlapping = String::new();
    let mut current_chunk = String::new();

    for s in sentences {
        current_chunk.push_str(&s);
        let overlapping_word_count = word_count(overlapping.as_str());
        let current_word_count = word_count(current_chunk.as_str());
        if overlapping_word_count + current_word_count > max_chunk_size {
            // chunk filled up, push to result
            res.push(overlapping + current_chunk.as_str());

            // update overlapping
            overlapping = get_tail_sentences(&current_chunk, max_overlapping_size).join("");

            // clear the container
            current_chunk.clear()
        }
    }
    if !current_chunk.is_empty() {
        // push the last chunk that does not fill up a chunk
        res.push(overlapping + current_chunk.as_str());
    }
    res
}

/// get the tail of the sentences of a long string.
fn get_tail_sentences(string: &str, max_size: usize) -> Vec<String> {
    let mut res: Vec<String> = vec![];
    for s in split_sentence_bounds(string).iter().rev() {
        if word_count(s.as_str()) + word_count(res.join("").as_str()) <= max_size {
            res.push(s.to_string());
        } else {
            break;
        }
    }
    res.reverse();
    res
}

/// count the words
#[pyfunction]
pub(crate) fn word_count(string: &str) -> usize {
    string
        .split_word_bounds()
        .filter(|s| !s.trim().is_empty())
        .count()
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(split_word_bounds, m)?)?;
    m.add_function(wrap_pyfunction!(word_count, m)?)?;
    m.add_function(wrap_pyfunction!(split_sentence_bounds, m)?)?;
    m.add_function(wrap_pyfunction!(split_into_chunks, m)?)?;
    Ok(())
}
