#![cfg_attr(feature = "stubgen", allow(dead_code, unused,))]

use pyo3::prelude::*;
use whichlang::{Lang, detect_language as dl};

#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

/// Converts a WhichLang language enum variant to its full name in the native script.
///
/// Args:
///     lang: The WhichLang language enum variant to convert.
///
/// Returns:
///     A string containing the language name in its native script (e.g., "English", "日本語").
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

/// Detects the language of a given string and returns its full native name.
///
/// This function uses the whichlang library to detect the primary language
/// of the input text and converts it to a human-readable string.
///
/// Args:
///     string: The input text string to analyze.
///
/// Returns:
///     A string containing the detected language name in its native script.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
#[pyo3(signature = (string))]
fn detect_language(string: &str) -> String {
    convert_to_string_respectively(dl(string))
}

/// Checks if the given string is written in Simplified Chinese.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is Mandarin Chinese, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_chinese(string: &str) -> bool {
    dl(string) == Lang::Cmn
}

/// Checks if the given string is written in English.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is English, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_english(string: &str) -> bool {
    dl(string) == Lang::Eng
}

/// Checks if the given string is written in Japanese.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is Japanese, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_japanese(string: &str) -> bool {
    dl(string) == Lang::Jpn
}

/// Checks if the given string is written in Korean.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is Korean, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_korean(string: &str) -> bool {
    dl(string) == Lang::Kor
}

/// Checks if the given string is written in Arabic.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is Arabic, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_arabic(string: &str) -> bool {
    dl(string) == Lang::Ara
}

/// Checks if the given string is written in Russian.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is Russian, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_russian(string: &str) -> bool {
    dl(string) == Lang::Rus
}

/// Checks if the given string is written in German.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is German, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_german(string: &str) -> bool {
    dl(string) == Lang::Deu
}

/// Checks if the given string is written in French.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is French, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_french(string: &str) -> bool {
    dl(string) == Lang::Fra
}

/// Checks if the given string is written in Hindi.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is Hindi, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_hindi(string: &str) -> bool {
    dl(string) == Lang::Hin
}

/// Checks if the given string is written in Italian.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is Italian, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_italian(string: &str) -> bool {
    dl(string) == Lang::Ita
}

/// Checks if the given string is written in Dutch.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is Dutch, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_dutch(string: &str) -> bool {
    dl(string) == Lang::Nld
}

/// Checks if the given string is written in Portuguese.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is Portuguese, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_portuguese(string: &str) -> bool {
    dl(string) == Lang::Por
}

/// Checks if the given string is written in Swedish.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is Swedish, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_swedish(string: &str) -> bool {
    dl(string) == Lang::Swe
}

/// Checks if the given string is written in Turkish.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is Turkish, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_turkish(string: &str) -> bool {
    dl(string) == Lang::Tur
}

/// Checks if the given string is written in Vietnamese.
///
/// Args:
///     string: The input text string to check.
///
/// Returns:
///     True if the detected language is Vietnamese, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_vietnamese(string: &str) -> bool {
    dl(string) == Lang::Vie
}

/// Registers all language detection functions with the Python module.
///
/// Args:
///     _: The Python interpreter instance.
///     m: The Python module to register with.
///
/// Returns:
///     PyResult<()> indicating success.
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
