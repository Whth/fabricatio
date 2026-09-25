//! Which script a run is written in.

use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

use super::{Measure, Metrics, Reported, report, share};
use crate::text::{is_cjk, is_whitespace};

/// The evidence a script reading leaves behind: how the prose's characters divide by script.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(frozen, get_all)]
pub struct ScriptReport {
    /// How many characters the corpus holds, whitespace included.
    chars: usize,

    /// How many of them are not whitespace; every share below is over these.
    non_space: usize,

    /// How many are CJK.
    cjk: usize,

    /// How many are ASCII letters.
    latin: usize,

    /// How many are ASCII digits.
    digits: usize,

    /// How many are anything else: punctuation, other scripts, symbols.
    other: usize,

    /// The share of the non-whitespace characters that is CJK.
    cjk_share: f64,

    /// The share of the non-whitespace characters that is Latin.
    latin_share: f64,

    /// The share of the non-whitespace characters that is a digit.
    digit_share: f64,

    /// The share of the non-whitespace characters that is anything else.
    other_share: f64,
}

impl ScriptReport {
    /// Read one corpus's characters.
    fn of(scalars: impl Iterator<Item = char>) -> Self {
        let mut report = Self {
            chars: 0,
            non_space: 0,
            cjk: 0,
            latin: 0,
            digits: 0,
            other: 0,
            cjk_share: 0.0,
            latin_share: 0.0,
            digit_share: 0.0,
            other_share: 0.0,
        };
        for scalar in scalars {
            report.chars += 1;
            if is_whitespace(scalar) {
                continue;
            }
            report.non_space += 1;
            if is_cjk(scalar) {
                report.cjk += 1;
            } else if scalar.is_ascii_alphabetic() {
                report.latin += 1;
            } else if scalar.is_ascii_digit() {
                report.digits += 1;
            } else {
                report.other += 1;
            }
        }
        report.cjk_share = share(report.cjk, report.non_space);
        report.latin_share = share(report.latin, report.non_space);
        report.digit_share = share(report.digits, report.non_space);
        report.other_share = share(report.other, report.non_space);
        report
    }
}

impl Reported for ScriptReport {
    const MEASURE: &'static str = "script";

    fn metrics(&self) -> Metrics {
        report(
            Self::MEASURE,
            [
                ("chars", self.chars as f64),
                ("non_space", self.non_space as f64),
                ("cjk", self.cjk as f64),
                ("cjk_share", self.cjk_share),
                ("latin_share", self.latin_share),
                ("digit_share", self.digit_share),
                ("other_share", self.other_share),
            ],
        )
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl ScriptReport {
    /// Every number this reading reported, named `script.<metric>`.
    fn metrics(&self) -> Metrics {
        <Self as Reported>::metrics(self)
    }
}

/// Which script a run is written in.
///
/// Nothing here is configurable: a character is CJK, Latin, a digit or neither by its own code
/// point, and the share of each is what a report compares.
pub(crate) struct Script;

impl Script {}

impl<T> Measure<T> for Script
where
    T: AsRef<str> + ?Sized,
{
    type Evidence = ScriptReport;

    fn measure<'a, C>(&self, corpus: C) -> ScriptReport
    where
        C: IntoIterator<Item = &'a T>,
        T: 'a,
    {
        ScriptReport::of(
            corpus
                .into_iter()
                .flat_map(|text| text.as_ref().chars())
                .collect::<Vec<char>>()
                .into_iter(),
        )
    }
}

/// Measures which script a run is written in.
///
/// Every character is counted once, whitespace included, so the shares of the CJK, Latin and digit
/// characters are over the non-whitespace text and a Chinese run can be told from an English one.
///
/// Args:
///     text: The text to read.
///
/// Returns:
///     The counts and shares of each script.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
#[pyo3(signature = (text))]
fn measure_script(text: &str) -> ScriptReport {
    Script.measure(std::iter::once(text))
}

/// Registers the script measure with the Python module.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<ScriptReport>()?;
    m.add_function(wrap_pyfunction!(measure_script, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::text::IDEOGRAPHS;

    /// Katakana, outside every Han block: the measure deliberately counts no kana as CJK.
    const KATAKANA: [char; 4] = ['\u{30ab}', '\u{30bf}', '\u{30ab}', '\u{30ca}'];

    /// The first `count` ideographs as one text.
    fn ideographs(count: usize) -> String {
        IDEOGRAPHS[..count].iter().collect()
    }

    #[test]
    fn measures_the_cjk_share_of_the_non_whitespace_characters() {
        assert_eq!(
            ScriptReport::of(format!("{}abc", ideographs(2)).chars()).cjk_share,
            0.4
        );
        let spaced: String = ideographs(3).chars().flat_map(|c| [c, ' ']).collect();
        assert_eq!(ScriptReport::of(spaced.chars()).cjk_share, 1.0);
        assert_eq!(
            ScriptReport::of(format!("\u{1c}{}\u{1f}", ideographs(1)).chars()).cjk_share,
            1.0
        );
        assert_eq!(ScriptReport::of("abc".chars()).cjk_share, 0.0);
        assert_eq!(ScriptReport::of(KATAKANA.into_iter()).cjk_share, 0.0);
        assert_eq!(ScriptReport::of("".chars()).cjk_share, 0.0);
        assert_eq!(ScriptReport::of(" \n\t ".chars()).cjk_share, 0.0);
    }

    #[test]
    fn divides_the_text_by_script_without_losing_a_character() {
        let report = ScriptReport::of(format!("{} abc 12 ., ", ideographs(2)).chars());
        assert_eq!(report.chars, 13);
        assert_eq!(report.non_space, 9);
        assert_eq!(
            (report.cjk, report.latin, report.digits, report.other),
            (2, 3, 2, 2)
        );
        assert_eq!(report.latin_share, 3.0 / 9.0);
        assert_eq!(report.digit_share, 2.0 / 9.0);
        assert_eq!(report.other_share, 2.0 / 9.0);
        assert_eq!(
            report.cjk + report.latin + report.digits + report.other,
            report.non_space
        );
    }

    #[test]
    fn reads_a_whole_corpus_as_one_text() {
        let pair = ideographs(2);
        let latin = String::from("abc");
        let joined = format!("{pair}{latin}");
        let split = Script.measure([&pair, &latin]);
        let whole = Script.measure([&joined]);
        assert_eq!(split.chars, whole.chars);
        assert_eq!(split.cjk, whole.cjk);
        assert_eq!(split.latin, whole.latin);
        assert_eq!(split.cjk_share, whole.cjk_share);
    }
}
