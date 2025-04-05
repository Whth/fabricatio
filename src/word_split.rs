use pyo3::prelude::*;
use unicode_segmentation::UnicodeSegmentation;

/// split the string into words
#[pyfunction]
fn split_word_bounds(string: &str) ->Vec<String>{
    string.split_word_bounds().map(|s| s.to_string()).collect()
}


/// split the string into sentences
#[pyfunction]
fn split_sentence_bounds(string: &str) ->Vec<String>{
    string.split_sentence_bounds().map(|s| s.to_string()).collect()
}



#[pyfunction]
#[pyo3(signature = (string, max_chunk_size, max_overlapping_rate=0.3))]
fn split_into_chunks(string: &str, max_chunk_size: usize, max_overlapping_rate: f64) -> Vec<String> {
    let sentences=split_sentence_bounds(string);
    let mut res=vec![];
    let max_overlapping_size = (max_overlapping_rate * max_chunk_size as f64) as usize;
    let mut overlapping=String::new();
    let mut current_chunk=String::new();

    for s in sentences{
       let sentence_word_count =word_count(s.as_str());
        let overlapping_word_count = word_count(overlapping.as_str());
        let current_word_count = word_count(current_chunk.as_str());
        if overlapping_word_count + current_word_count+ sentence_word_count <= max_chunk_size {
            current_chunk.push_str(&s)
        } else {
            res.push(overlapping+current_chunk.as_str());
            overlapping=get_tail_sentences(&current_chunk,max_overlapping_size).join("");
            current_chunk.clear()
        }

    }
    res
}


/// get the tail of the sentences of a long string.
fn get_tail_sentences(string:&str,max_size:usize)->Vec<String>{
    let mut res:Vec<String>=vec![];
    for s in split_sentence_bounds(string).iter().rev(){
        if word_count(s.as_str())+res.iter().map(|s| word_count(s)).sum::<usize>()<=max_size{
            res.push(s.to_string());
        }else{
            break;
        }
    }
    res.reverse();
    res
}

/// count the words
#[pyfunction]
pub(crate) fn word_count(string: &str) -> usize {
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