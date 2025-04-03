use pyo3::prelude::*;
use unicode_segmentation::UnicodeSegmentation;


/// split the string into words
#[pyfunction]
fn split_word_bounds(string: String) ->Vec<String>{
    string.as_str().split_word_bounds().map(|s| s.to_string()).collect()
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
    Ok(())
}