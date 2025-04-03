use pyo3::prelude::*;
use whichlang::{detect_language as dl, Lang};


/// convert the language to a string
pub(crate) fn convert_to_string_respectively(lang:Lang)->String{
    match lang {
        Lang::Ara => "العربية".to_string(),    // Arabic
        Lang::Cmn => "简体中文".to_string(),        // Mandarin Chinese
        Lang::Deu => "Deutsch".to_string(),    // German
        Lang::Eng => "English".to_string(),    // English
        Lang::Fra => "Français".to_string(),   // French
        Lang::Hin => "हिन्दी".to_string(),      // Hindi
        Lang::Ita => "Italiano".to_string(),   // Italian
        Lang::Jpn => "日本語".to_string(),       // Japanese
        Lang::Kor => "한국어".to_string(),       // Korean
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
#[pyfunction]
#[pyo3(signature = (string))]
fn detect_language(string: String) -> String {
    convert_to_string_respectively(dl(string.as_str()))
}


/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(detect_language,m)?)?;
    Ok(())
}