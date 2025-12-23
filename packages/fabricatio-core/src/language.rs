use pyo3::prelude::*;
use whichlang::{Lang, detect_language as dl};

use pyo3_stub_gen::derive::*;

/// convert the language to a string
pub(crate) fn convert_to_string_respectively(lang: Lang) -> String {
    match lang {
        Lang::Ara => "العربية".to_string(),    // Arabic
        Lang::Cmn => "简体中文".to_string(),   // Mandarin Chinese
        Lang::Deu => "Deutsch".to_string(),    // German
        Lang::Eng => "English".to_string(),    // English
        Lang::Fra => "Français".to_string(),   // French
        Lang::Hin => "हिन्दी".to_string(),      // Hindi
        Lang::Ita => "Italiano".to_string(),   // Italian
        Lang::Jpn => "日本語".to_string(),     // Japanese
        Lang::Kor => "한국어".to_string(),     // Korean
        Lang::Nld => "Nederlands".to_string(), // Dutch
        Lang::Por => "Português".to_string(),  // Portuguese
        Lang::Rus => "Русский".to_string(),    // Russian
        Lang::Spa => "Español".to_string(),    // Spanish
        Lang::Swe => "Svenska".to_string(),    // Swedish
        Lang::Tur => "Türkçe".to_string(),     // Turkish
        Lang::Vie => "Tiếng Việt".to_string(), // Vietnamese
    }
}

/// detect the language of a string
#[gen_stub_pyfunction]
#[pyfunction]
#[pyo3(signature = (string))]
fn detect_language(string: &str) -> String {
    convert_to_string_respectively(dl(string))
}

#[gen_stub_pyfunction]
#[pyfunction]

fn is_chinese(string: &str) -> bool {
    dl(string) == Lang::Cmn
}
#[gen_stub_pyfunction]
#[pyfunction]
fn is_english(string: &str) -> bool {
    dl(string) == Lang::Eng
}
#[gen_stub_pyfunction]
#[pyfunction]
fn is_japanese(string: &str) -> bool {
    dl(string) == Lang::Jpn
}
#[gen_stub_pyfunction]
#[pyfunction]
fn is_korean(string: &str) -> bool {
    dl(string) == Lang::Kor
}
#[gen_stub_pyfunction]
#[pyfunction]
fn is_arabic(string: &str) -> bool {
    dl(string) == Lang::Ara
}
#[gen_stub_pyfunction]
#[pyfunction]
fn is_russian(string: &str) -> bool {
    dl(string) == Lang::Rus
}

#[gen_stub_pyfunction]
#[pyfunction]
fn is_german(string: &str) -> bool {
    dl(string) == Lang::Deu
}

#[gen_stub_pyfunction]
#[pyfunction]
fn is_french(string: &str) -> bool {
    dl(string) == Lang::Fra
}
#[gen_stub_pyfunction]
#[pyfunction]
fn is_hindi(string: &str) -> bool {
    dl(string) == Lang::Hin
}
#[gen_stub_pyfunction]
#[pyfunction]
fn is_italian(string: &str) -> bool {
    dl(string) == Lang::Ita
}
#[gen_stub_pyfunction]
#[pyfunction]
fn is_dutch(string: &str) -> bool {
    dl(string) == Lang::Nld
}
#[gen_stub_pyfunction]
#[pyfunction]
fn is_portuguese(string: &str) -> bool {
    dl(string) == Lang::Por
}
#[gen_stub_pyfunction]
#[pyfunction]
fn is_swedish(string: &str) -> bool {
    dl(string) == Lang::Swe
}
#[gen_stub_pyfunction]
#[pyfunction]
fn is_turkish(string: &str) -> bool {
    dl(string) == Lang::Tur
}
#[gen_stub_pyfunction]
#[pyfunction]
fn is_vietnamese(string: &str) -> bool {
    dl(string) == Lang::Vie
}
/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(detect_language, m)?)?;
    m.add_function(wrap_pyfunction!(is_chinese, m)?)?;
    m.add_function(wrap_pyfunction!(is_english, m)?)?;
    m.add_function(wrap_pyfunction!(is_japanese, m)?)?;
    m.add_function(wrap_pyfunction!(is_korean, m)?)?;
    m.add_function(wrap_pyfunction!(is_arabic, m)?)?;
    m.add_function(wrap_pyfunction!(is_russian, m)?)?;
    m.add_function(wrap_pyfunction!(is_german, m)?)?;
    m.add_function(wrap_pyfunction!(is_french, m)?)?;
    m.add_function(wrap_pyfunction!(is_hindi, m)?)?;
    m.add_function(wrap_pyfunction!(is_italian, m)?)?;
    m.add_function(wrap_pyfunction!(is_dutch, m)?)?;
    m.add_function(wrap_pyfunction!(is_portuguese, m)?)?;
    m.add_function(wrap_pyfunction!(is_swedish, m)?)?;
    m.add_function(wrap_pyfunction!(is_turkish, m)?)?;
    m.add_function(wrap_pyfunction!(is_vietnamese, m)?)?;
    Ok(())
}
