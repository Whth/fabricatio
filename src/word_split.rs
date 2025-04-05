use pyo3::prelude::*;
use unicode_segmentation::UnicodeSegmentation;

/// split the string into words
#[pyfunction]
fn split_word_bounds(string: String) ->Vec<String>{
    string.as_str().split_word_bounds().map(|s| s.to_string()).collect()
}


/// split the string into sentences
#[pyfunction]
fn split_sentence_bounds(string: String) ->Vec<String>{
    string.as_str().split_sentence_bounds().map(|s| s.to_string()).collect()
}


/// split the string into chunks
#[pyfunction]
fn split_into_chunks(string: String, max_chunk_size: isize) -> Vec<String> {
    let sentences = split_sentence_bounds(string);
    let mut chunks = Vec::new();
    let mut current_chunk = String::new();
    let mut current_size = 0;

    for sentence in sentences {
        let word_count = sentence.split_word_bounds().count() as isize;
        if current_size + word_count > max_chunk_size {
            if !current_chunk.is_empty() {
                chunks.push(current_chunk);
                current_chunk = String::new();
                current_size = 0;
            }
        }
        current_chunk.push_str(&sentence);
        current_size += word_count;
    }

    if !current_chunk.is_empty() {
        chunks.push(current_chunk);
    }

    chunks
}


/// count the words
#[pyfunction]
pub(crate) fn word_count(string: String) -> usize {
    string.split_word_bounds().count()
}






/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(split_word_bounds,m)?)?;
    m.add_function(wrap_pyfunction!(word_count,m)?)?;
    m.add_function(wrap_pyfunction!(split_sentence_bounds,m)?)?;
    m.add_function(wrap_pyfunction!(split_into_chunks,m)?)?;
    Ok(())
}