//! How much short vocabulary a run recycles.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

use super::{Knobs, Measure, Metrics, Reported, report, share};
use crate::text::compact;
use crate::text::ngram::{MAX_N, NGramRecycling, NGramTally};

/// The n-gram counts of one size and the grams a report names for it.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(frozen, get_all, skip_from_py_object)]
#[derive(Clone)]
pub struct GramTable {
    /// How many characters one n-gram of this table spans.
    size: usize,

    /// How many n-grams of this size the prose holds.
    grams: usize,

    /// How many of those n-grams are distinct.
    distinct: usize,

    /// How many distinct n-grams occur more than once.
    repeated: usize,

    /// How much of the distinct vocabulary this size repeats at all.
    share: f64,

    /// The most frequent n-grams of this size, most frequent first, ties in code point order.
    tops: Vec<(String, u32)>,
}

impl GramTable {
    /// Read one size over the whole prose: its counts and the grams a report names for it.
    fn of(chars: &[char], size: usize, tops: usize) -> Self {
        let tally = NGramTally::of(chars, size, tops);
        Self {
            size: tally.size,
            grams: tally.total_slots,
            distinct: tally.distinct_grams,
            repeated: tally.repeated_grams,
            share: share(tally.repeated_grams, tally.distinct_grams),
            tops: tally.grams,
        }
    }
}

/// The evidence a vocabulary reading leaves behind: the repeated n-grams and the window rates.
///
/// The corpus is read as one stream — windows are cut across everything the measure was handed —
/// so the rate describes the prose and not how it was divided into scenes.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(frozen, get_all)]
pub struct VocabularyReport {
    /// How many characters one n-gram spans.
    size: usize,

    /// How many n-grams the prose holds.
    grams: usize,

    /// How many of those n-grams are distinct.
    distinct: usize,

    /// How many distinct n-grams occur more than once.
    repeated: usize,

    /// How many windows the rate was measured over; `0` when the prose holds no n-gram.
    windows: usize,

    /// The mean number of n-grams per 1000 that repeat inside their own window.
    recycled_per_1k: f64,

    /// How much of the distinct vocabulary the prose repeats at all.
    repeat_share: f64,

    /// One table per n-gram size from 1 to 6, each naming its own most frequent grams.
    ///
    /// Every size is read, not only the calibrated one the counts and the rate describe: a
    /// character, a pair and a phrase repeat on different scales, and which one a run recycles is
    /// what the tables answer.
    tables: Vec<GramTable>,
}

impl VocabularyReport {
    /// Read one run of prose: how much of its n-gram vocabulary comes back.
    fn of(chars: &[char], knobs: &Knobs) -> Self {
        let size = knobs.vocab_size;
        let recycling = NGramRecycling::of(chars, size, knobs.vocab_window);
        let counted = NGramTally::of(chars, size, 0);
        Self {
            size: counted.size,
            grams: counted.total_slots,
            distinct: counted.distinct_grams,
            repeated: counted.repeated_grams,
            repeat_share: share(counted.repeated_grams, counted.distinct_grams),
            windows: recycling.windows,
            recycled_per_1k: recycling.recycled_per_1k,
            tables: (1..=MAX_N)
                .map(|size| GramTable::of(chars, size, knobs.vocab_tops))
                .collect(),
        }
    }
}

impl Reported for VocabularyReport {
    const MEASURE: &'static str = "vocabulary";

    fn metrics(&self) -> Metrics {
        report(
            Self::MEASURE,
            [
                ("size", self.size as f64),
                ("grams", self.grams as f64),
                ("distinct", self.distinct as f64),
                ("repeated", self.repeated as f64),
                ("repeat_share", self.repeat_share),
                ("windows", self.windows as f64),
                ("recycled_per_1k", self.recycled_per_1k),
            ],
        )
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl VocabularyReport {
    /// Every number this reading reported, named `vocabulary.<metric>`.
    fn metrics(&self) -> Metrics {
        <Self as Reported>::metrics(self)
    }
}

/// How much short vocabulary a run recycles.
///
/// The vocabulary is cut into n-grams of [`Knobs::vocab_size`] characters over the whitespace-free
/// text, one stream for every script, and every window of [`Knobs::vocab_window`] n-grams is
/// measured on its own, so the rate describes the prose rather than the run's length.
pub(crate) struct Vocabulary {
    /// The sizes the run is read at.
    knobs: Knobs,
}

impl Vocabulary {
    /// The measure, reading a run by `knobs`.
    pub(super) fn new(knobs: Knobs) -> Self {
        Self { knobs }
    }
}

impl<T> Measure<T> for Vocabulary
where
    T: AsRef<str> + ?Sized,
{
    type Evidence = VocabularyReport;

    fn measure<'a, C>(&self, corpus: C) -> VocabularyReport
    where
        C: IntoIterator<Item = &'a T>,
        T: 'a,
    {
        let prose: String = corpus.into_iter().map(AsRef::as_ref).collect();
        VocabularyReport::of(&compact(&prose), &self.knobs)
    }
}

/// Measures how much of a run's short vocabulary repeats.
///
/// Whitespace is dropped, the prose is cut into character n-grams and every window of the run is
/// measured on its own, so a long run does not score as more repetitive than a short one. Unlike a
/// word count this needs no word boundaries and no stopword list, which is what lets the same rule
/// read a Chinese and an English run.
///
/// Args:
///     text: The prose to measure.
///     knobs: The sizes to read the run at; the calibrated ones when omitted.
///
/// Returns:
///     The n-gram counts and window rate of the calibrated size, and one table per size from 1 to
///     6, each naming its most frequent grams.
///
/// Raises:
///     ValueError: A `vocab_size` outside `1..=6`, or a size or window below 1 in `knobs`.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
#[pyo3(signature = (text, knobs=None))]
fn measure_vocabulary(text: &str, knobs: Option<Knobs>) -> PyResult<VocabularyReport> {
    let knobs = knobs.unwrap_or_default();
    knobs.check().map_err(PyValueError::new_err)?;
    Ok(Vocabulary::new(knobs).measure(std::iter::once(text)))
}

/// Registers the vocabulary measure with the Python module.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<GramTable>()?;
    m.add_class::<VocabularyReport>()?;
    m.add_function(wrap_pyfunction!(measure_vocabulary, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn counts_the_grams_of_the_whitespace_free_prose() {
        // "abab" holds three 2-grams: ab, ba and ab — two distinct, one of them repeated twice.
        let report = VocabularyReport::of(
            &compact("a ba b"),
            &Knobs {
                vocab_size: 2,
                ..Knobs::default()
            },
        );
        assert_eq!(report.size, 2);
        assert_eq!(report.grams, 3);
        assert_eq!(report.distinct, 2);
        assert_eq!(report.repeated, 1);
        assert_eq!(report.repeat_share, 0.5);
        // The tables run in size order, so index 1 holds the 2-grams: the same counts, and every
        // gram named, single ones included.
        let named = &report.tables[1];
        assert_eq!(
            (named.size, named.grams, named.distinct, named.repeated),
            (2, 3, 2, 1)
        );
        assert_eq!(
            named.tops,
            vec![("ab".to_string(), 2), ("ba".to_string(), 1)]
        );
    }

    #[test]
    fn names_every_gram_size_from_one_to_six() {
        let report = VocabularyReport::of(&compact("abcabc"), &Knobs::default());
        assert_eq!(
            report
                .tables
                .iter()
                .map(|table| table.size)
                .collect::<Vec<_>>(),
            (1..=MAX_N).collect::<Vec<_>>()
        );
        // Every 1-gram occurs twice and the whole text once, ties read in code point order.
        assert_eq!(
            report.tables[0].tops,
            vec![
                ("a".to_string(), 2),
                ("b".to_string(), 2),
                ("c".to_string(), 2)
            ]
        );
        assert_eq!(
            report.tables[MAX_N - 1].tops,
            vec![("abcabc".to_string(), 1)]
        );
    }

    #[test]
    fn names_no_more_grams_than_the_knobs_ask_for() {
        let report = VocabularyReport::of(
            &compact("abcabcabc"),
            &Knobs {
                vocab_tops: 1,
                ..Knobs::default()
            },
        );
        assert_eq!(report.tables[2].tops, vec![("abc".to_string(), 3)]);
        assert_eq!(report.tables[2].distinct, 3);
    }

    #[test]
    fn measures_a_run_too_short_for_its_window_as_the_window_it_fits_in() {
        let report = VocabularyReport::of(
            &compact("abab"),
            &Knobs {
                vocab_size: 2,
                ..Knobs::default()
            },
        );
        assert_eq!(report.grams, 3);
        assert_eq!(report.windows, 1);
        assert_eq!(report.recycled_per_1k, 666.6666666666666);
    }

    #[test]
    fn reads_a_run_without_a_single_gram_as_nothing() {
        let report = VocabularyReport::of(&compact("a"), &Knobs::default());
        assert_eq!(report.grams, 0);
        assert_eq!(report.windows, 0);
        assert_eq!(report.recycled_per_1k, 0.0);
        assert_eq!(report.tables[2].grams, 0);
        assert!(report.tables[2].tops.is_empty());
        // A size short enough to see something still counts it.
        assert_eq!(report.tables[0].tops, vec![("a".to_string(), 1)]);
    }

    #[test]
    fn reads_every_document_of_a_corpus_as_one_stream() {
        let split = Vocabulary::new(Knobs::default()).measure(["abab", "abab"]);
        let whole = Vocabulary::new(Knobs::default()).measure(["abababab"]);
        assert_eq!(split.grams, whole.grams);
        assert_eq!(split.distinct, whole.distinct);
    }
}
