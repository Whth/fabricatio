//! The sizes and thresholds every measure reads a run by.

use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

use crate::text::ngram;

/// Every size and threshold the measures read a run by.
///
/// A measure is built with one of these, so a run can be scored at other sizes than the calibrated
/// ones without touching this crate. An argument left `None` at construction keeps its calibrated
/// value, which is what the Python side passes while the package configuration leaves a knob
/// unset.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(frozen, get_all, from_py_object)]
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Knobs {
    /// How many characters one n-gram spans when scene pairs are shingled.
    ///
    /// Long enough that sharing one means more than shared vocabulary.
    pub(crate) pair_size: usize,

    /// How many characters one n-gram spans when a seam is compared.
    ///
    /// Short enough to survive a paraphrase at the seam.
    pub(crate) seam_size: usize,

    /// How many characters are read from each side of a seam.
    pub(crate) seam_window: usize,

    /// The overlap from which a pair or a seam is reported as a repetition.
    ///
    /// Clean runs measured under `0.03`; seams that restaged the previous scene, `0.10`-`0.14`.
    pub(crate) echo_warn: f64,

    /// How many characters one vocabulary n-gram spans.
    ///
    /// Characters, not words: one stream measures every script, so no metric has to know which
    /// language the run is in. Three characters are a word in Chinese and a word fragment in
    /// English, which is why the numbers compare runs of one corpus rather than prose in the
    /// abstract.
    pub(crate) vocab_size: usize,

    /// How many n-grams make up one vocabulary window.
    ///
    /// A run is measured window by window and the windows are averaged, so the number does not
    /// follow the run's length: measured over a whole manuscript, a long run would always look
    /// more repetitive than a short one, because it gave its n-grams more chances to meet again.
    pub(crate) vocab_window: usize,

    /// How many of the most frequent n-grams each size's table names.
    pub(crate) vocab_tops: usize,
}

impl Default for Knobs {
    /// The calibrated knobs: the sizes every number in a scorecard was taken at.
    fn default() -> Self {
        Self {
            pair_size: 12,
            seam_size: 8,
            seam_window: 300,
            echo_warn: 0.05,
            vocab_size: 3,
            vocab_window: 1000,
            vocab_tops: 30,
        }
    }
}

impl Knobs {
    /// Whether every knob is in the range its measure can read.
    pub(crate) fn check(&self) -> Result<(), String> {
        ngram::check_size(self.vocab_size)?;
        if self.pair_size == 0 {
            return Err("pair_size must be at least 1".to_string());
        }
        if self.seam_size == 0 {
            return Err("seam_size must be at least 1".to_string());
        }
        if self.seam_window == 0 {
            return Err("seam_window must be at least 1".to_string());
        }
        if self.vocab_window == 0 {
            return Err("vocab_window must be at least 1".to_string());
        }
        Ok(())
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl Knobs {
    /// The knobs to measure a run by; an argument left out keeps its calibrated value.
    #[new]
    #[allow(clippy::too_many_arguments)]
    #[pyo3(signature = (pair_size=None, seam_size=None, seam_window=None, echo_warn=None, vocab_size=None, vocab_window=None, vocab_tops=None))]
    fn new(
        pair_size: Option<usize>,
        seam_size: Option<usize>,
        seam_window: Option<usize>,
        echo_warn: Option<f64>,
        vocab_size: Option<usize>,
        vocab_window: Option<usize>,
        vocab_tops: Option<usize>,
    ) -> Self {
        let calibrated = Self::default();
        Self {
            pair_size: pair_size.unwrap_or(calibrated.pair_size),
            seam_size: seam_size.unwrap_or(calibrated.seam_size),
            seam_window: seam_window.unwrap_or(calibrated.seam_window),
            echo_warn: echo_warn.unwrap_or(calibrated.echo_warn),
            vocab_size: vocab_size.unwrap_or(calibrated.vocab_size),
            vocab_window: vocab_window.unwrap_or(calibrated.vocab_window),
            vocab_tops: vocab_tops.unwrap_or(calibrated.vocab_tops),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keeps_the_calibrated_value_of_every_knob_left_out() {
        let knobs = Knobs::new(Some(4), None, None, None, None, None, None);
        assert_eq!(
            knobs,
            Knobs {
                pair_size: 4,
                ..Knobs::default()
            }
        );
    }

    #[test]
    fn refuses_a_knob_its_measure_cannot_read() {
        assert!(Knobs::default().check().is_ok());
        assert!(
            Knobs::new(Some(0), None, None, None, None, None, None)
                .check()
                .is_err()
        );
        assert!(
            Knobs::new(None, Some(0), None, None, None, None, None)
                .check()
                .is_err()
        );
        assert!(
            Knobs::new(None, None, Some(0), None, None, None, None)
                .check()
                .is_err()
        );
        assert!(
            Knobs::new(None, None, None, None, Some(0), None, None)
                .check()
                .is_err()
        );
        assert!(
            Knobs::new(None, None, None, None, Some(7), None, None)
                .check()
                .is_err()
        );
        assert!(
            Knobs::new(None, None, None, None, None, Some(0), None)
                .check()
                .is_err()
        );
    }
}
