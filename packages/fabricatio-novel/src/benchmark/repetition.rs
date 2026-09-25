//! How much a run's scenes repeat each other.

use std::cmp::Ordering;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

use super::{Knobs, Measure, Metrics, Reported, report};
use crate::text::{compact, compact_slice};

/// The distinct n-grams of one text, held as the start indices of the slices that cut them.
///
/// The grams are never materialised: sorting the indices by the slice each one points at puts them
/// in the order a set of strings would, exactly and without hashing, and a slice is only read while
/// two candidates are compared.
struct Grams<'a> {
    /// The scalar values the grams are cut from.
    chars: &'a [char],

    /// One start index per distinct gram, sorted by that gram.
    starts: Vec<u32>,

    /// How many characters one gram spans.
    size: usize,
}

impl<'a> Grams<'a> {
    /// Read the distinct n-grams of a text.
    fn of(chars: &'a [char], size: usize) -> Self {
        let mut grams: Vec<(&[char], u32)> = chars
            .windows(size)
            .enumerate()
            .map(|(start, gram)| (gram, start as u32))
            .collect();
        grams.sort_unstable_by(|left, right| left.0.cmp(right.0));
        grams.dedup_by(|left, right| left.0 == right.0);
        Self {
            chars,
            starts: grams.into_iter().map(|(_, start)| start).collect(),
            size,
        }
    }

    /// The gram one start index cuts out of the text.
    fn gram(&self, start: u32) -> &'a [char] {
        let start = start as usize;
        &self.chars[start..start + self.size]
    }

    /// The fraction of this text's distinct n-grams that also occur in `other`.
    ///
    /// Both sides are already sorted by gram, so one walk over each answers the whole overlap.
    fn overlap(&self, other: &Self) -> f64 {
        if self.starts.is_empty() {
            return 0.0;
        }
        let mut shared = 0;
        let (mut left, mut right) = (0, 0);
        while left < self.starts.len() && right < other.starts.len() {
            match self
                .gram(self.starts[left])
                .cmp(other.gram(other.starts[right]))
            {
                Ordering::Less => left += 1,
                Ordering::Greater => right += 1,
                Ordering::Equal => {
                    shared += 1;
                    left += 1;
                    right += 1;
                }
            }
        }
        shared as f64 / self.starts.len() as f64
    }
}

/// The evidence a repetition reading leaves behind: what every scene pair and every seam measured.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(frozen, get_all)]
pub struct RepetitionReport {
    /// The overlap of every scene pair: `(0, 1)` first, `(n-2, n-1)` last.
    pairs: Vec<f64>,

    /// The echo of every seam, in reading order.
    ///
    /// Each reading is a scene's closing stretch against its successor's opening.
    seams: Vec<f64>,

    /// The index of the worst pair, `(0, 1)` being `0`; `0` for a run without pairs.
    worst_pair_index: usize,

    /// The worst pair overlap, `0.0` for a run without pairs.
    max_pair: f64,

    /// The mean pair overlap.
    mean_pair: f64,

    /// The middle pair overlap: the middle reading, or the mean of the two middle ones.
    median_pair: f64,

    /// The pair overlap nine pairs in ten stay under.
    p90_pair: f64,

    /// How many pairs repeat more than the knobs' warning overlap.
    loud_pairs: usize,

    /// The index of the worst seam; `0` for a run without seams.
    worst_seam_index: usize,

    /// The worst seam echo, `0.0` for a run without seams.
    max_seam: f64,

    /// The mean seam echo.
    mean_seam: f64,

    /// How many seams echo more than the knobs' warning overlap.
    loud_seams: usize,
}

impl RepetitionReport {
    /// Summarise the two readings of one run: its pair overlaps and its seam echoes.
    fn of(pairs: Vec<f64>, seams: Vec<f64>, echo_warn: f64) -> Self {
        let mut ranked = pairs.clone();
        ranked.sort_unstable_by(f64::total_cmp);
        Self {
            worst_pair_index: Self::rank_of_worst(&pairs),
            max_pair: ranked.last().copied().unwrap_or(0.0),
            mean_pair: Self::mean(&ranked),
            median_pair: Self::median(&ranked),
            p90_pair: Self::percentile(&ranked, 0.9),
            loud_pairs: pairs.iter().filter(|overlap| **overlap > echo_warn).count(),
            worst_seam_index: Self::rank_of_worst(&seams),
            max_seam: seams.iter().copied().fold(0.0, f64::max),
            mean_seam: Self::mean(&seams),
            loud_seams: seams.iter().filter(|echo| **echo > echo_warn).count(),
            pairs,
            seams,
        }
    }

    /// The position of the largest reading; `0` when there is none.
    fn rank_of_worst(values: &[f64]) -> usize {
        values
            .iter()
            .enumerate()
            .max_by(|left, right| left.1.total_cmp(right.1))
            .map(|(index, _)| index)
            .unwrap_or(0)
    }

    /// The mean of the readings, `0.0` when there are none.
    fn mean(values: &[f64]) -> f64 {
        if values.is_empty() {
            0.0
        } else {
            values.iter().sum::<f64>() / values.len() as f64
        }
    }

    /// The middle reading of a sorted list; the mean of the two middle ones when it is even.
    fn median(ranked: &[f64]) -> f64 {
        match ranked.len() {
            0 => 0.0,
            count if count % 2 == 1 => ranked[count / 2],
            count => (ranked[count / 2 - 1] + ranked[count / 2]) / 2.0,
        }
    }

    /// The reading at or above which the top `share` of a sorted list lies: the nearest rank, so
    /// nine of ten readings are at or below the `0.9` one.
    fn percentile(ranked: &[f64], share: f64) -> f64 {
        if ranked.is_empty() {
            return 0.0;
        }
        let rank = (share * ranked.len() as f64).ceil() as usize;
        ranked[rank.saturating_sub(1).min(ranked.len() - 1)]
    }
}

impl Reported for RepetitionReport {
    const MEASURE: &'static str = "repetition";

    fn metrics(&self) -> Metrics {
        report(
            Self::MEASURE,
            [
                ("pairs", self.pairs.len() as f64),
                ("max_pair", self.max_pair),
                ("mean_pair", self.mean_pair),
                ("median_pair", self.median_pair),
                ("p90_pair", self.p90_pair),
                ("worst_pair_index", self.worst_pair_index as f64),
                ("loud_pairs", self.loud_pairs as f64),
                ("seams", self.seams.len() as f64),
                ("max_seam", self.max_seam),
                ("mean_seam", self.mean_seam),
                ("worst_seam_index", self.worst_seam_index as f64),
                ("loud_seams", self.loud_seams as f64),
            ],
        )
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl RepetitionReport {
    /// Every number this reading reported, named `repetition.<metric>`.
    fn metrics(&self) -> Metrics {
        <Self as Reported>::metrics(self)
    }
}

/// How much the scenes of a run repeat each other.
///
/// Every pair of scenes is shingled at [`Knobs::pair_size`] and every seam is read at
/// [`Knobs::seam_size`] over [`Knobs::seam_window`] characters from each side of it.
pub(crate) struct Repetition {
    /// The sizes the run is read at.
    knobs: Knobs,
}

impl Repetition {
    /// The measure, reading a run by `knobs`.
    pub(super) fn new(knobs: Knobs) -> Self {
        Self { knobs }
    }

    /// The overlap of every scene pair, in run order.
    fn pair_overlaps(texts: &[&str], size: usize) -> Vec<f64> {
        let bodies: Vec<Vec<char>> = texts.iter().map(|text| compact(text)).collect();
        let grams: Vec<Grams<'_>> = bodies.iter().map(|body| Grams::of(body, size)).collect();
        let mut overlaps = Vec::with_capacity(bodies.len().saturating_mul(bodies.len()) / 2);
        for (index, left) in grams.iter().enumerate() {
            for right in grams.iter().skip(index + 1) {
                overlaps.push(left.overlap(right));
            }
        }
        overlaps
    }

    /// The echo of every seam, in run order: a scene's closing stretch against its successor's
    /// opening.
    fn echoes(texts: &[&str], window: usize, size: usize) -> Vec<f64> {
        let bodies: Vec<Vec<char>> = texts.iter().map(|text| text.chars().collect()).collect();
        (0..bodies.len().saturating_sub(1))
            .map(|index| {
                let closing = &bodies[index];
                let opening = &bodies[index + 1];
                let left = compact_slice(
                    closing[closing.len().saturating_sub(window)..]
                        .iter()
                        .copied(),
                );
                let right = compact_slice(opening[..opening.len().min(window)].iter().copied());
                Grams::of(&left, size).overlap(&Grams::of(&right, size))
            })
            .collect()
    }
}

impl<T> Measure<T> for Repetition
where
    T: AsRef<str> + ?Sized,
{
    type Evidence = RepetitionReport;

    fn measure<'a, C>(&self, corpus: C) -> RepetitionReport
    where
        C: IntoIterator<Item = &'a T>,
        T: 'a,
    {
        let texts: Vec<&str> = corpus.into_iter().map(AsRef::as_ref).collect();
        RepetitionReport::of(
            Self::pair_overlaps(&texts, self.knobs.pair_size),
            Self::echoes(&texts, self.knobs.seam_window, self.knobs.seam_size),
            self.knobs.echo_warn,
        )
    }
}

/// Measures how much a run's scenes repeat each other.
///
/// Every pair of scenes is shingled, every seam is compared against its successor, and the readings
/// are summarised: the scorecard's repetition section is built from this one call.
///
/// Args:
///     scenes: The scenes' prose, in run order.
///     knobs: The sizes to read the run at; the calibrated ones when omitted.
///
/// Returns:
///     The pair overlaps, the seam echoes, and the numbers summarising them.
///
/// Raises:
///     ValueError: A size or window below 1 in `knobs`, or a vocabulary size above 6.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
#[pyo3(signature = (scenes, knobs=None))]
fn measure_repetition(scenes: Vec<String>, knobs: Option<Knobs>) -> PyResult<RepetitionReport> {
    let knobs = knobs.unwrap_or_default();
    knobs.check().map_err(PyValueError::new_err)?;
    Ok(Repetition::new(knobs).measure(scenes.iter()))
}

/// Registers the repetition measure with the Python module.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<RepetitionReport>()?;
    m.add_function(wrap_pyfunction!(measure_repetition, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The smallest brute force oracle for the pair overlaps: every distinct n-gram of the left
    /// scene, looked up in the right one.
    fn brute_overlap(left: &str, right: &str, size: usize) -> f64 {
        let grams = |text: &str| -> Vec<String> {
            let body: Vec<char> = text.chars().filter(|c| !c.is_whitespace()).collect();
            body.windows(size)
                .map(|gram| gram.iter().collect())
                .collect()
        };
        let left_grams = grams(left);
        let distinct: std::collections::HashSet<&String> = left_grams.iter().collect();
        if distinct.is_empty() {
            return 0.0;
        }
        let right_grams: std::collections::HashSet<String> = grams(right).into_iter().collect();
        distinct
            .iter()
            .filter(|gram| right_grams.contains(**gram))
            .count() as f64
            / distinct.len() as f64
    }

    #[test]
    fn overlaps_every_scene_pair_in_run_order() {
        let texts = ["abab", "ab", "cd"];
        let overlaps = Repetition::pair_overlaps(&texts, 2);
        assert_eq!(overlaps.len(), 3);
        for (index, (left, right)) in [(0, 1), (0, 2), (1, 2)].into_iter().enumerate() {
            let expected = brute_overlap(texts[left], texts[right], 2);
            assert!(
                (overlaps[index] - expected).abs() < 1e-12,
                "pair ({left}, {right}): {} != {expected}",
                overlaps[index]
            );
        }
    }

    #[test]
    fn echoes_every_seam_in_run_order() {
        let texts = ["xxabab", "ababzz", "cd"];
        let echoes = Repetition::echoes(&texts, 4, 2);
        assert_eq!(echoes.len(), 2);
        assert!((echoes[0] - brute_overlap("abab", "abab", 2)).abs() < 1e-12);
        assert!((echoes[1] - brute_overlap("abab", "cd", 2)).abs() < 1e-12);
    }

    #[test]
    fn summarises_the_pairs_and_seams_it_read() {
        let report = RepetitionReport::of(vec![0.0, 0.5, 1.0, 0.25], vec![0.1, 0.4], 0.2);
        assert_eq!(report.max_pair, 1.0);
        assert_eq!(report.worst_pair_index, 2);
        assert_eq!(report.mean_pair, 0.4375);
        assert_eq!(report.median_pair, 0.375);
        assert_eq!(report.p90_pair, 1.0);
        assert_eq!(report.loud_pairs, 3);
        assert_eq!(report.max_seam, 0.4);
        assert_eq!(report.mean_seam, 0.25);
        assert_eq!(report.worst_seam_index, 1);
        assert_eq!(report.loud_seams, 1);
    }

    #[test]
    fn reads_a_run_of_one_scene_as_no_pairs_and_no_seams() {
        let report = RepetitionReport::of(vec![], vec![], 0.05);
        assert_eq!(report.worst_pair_index, 0);
        assert_eq!(report.max_pair, 0.0);
        assert_eq!(report.median_pair, 0.0);
        assert_eq!(report.p90_pair, 0.0);
        assert_eq!(report.loud_pairs, 0);
        assert_eq!(report.max_seam, 0.0);
    }

    #[test]
    fn names_its_metrics_after_the_measure() {
        let metrics = RepetitionReport::of(vec![0.5], vec![], 0.05).metrics();
        let names: Vec<&str> = metrics.iter().map(|metric| metric.name.as_str()).collect();
        assert!(names.contains(&"repetition.max_pair"));
        assert!(names.contains(&"repetition.p90_pair"));
        assert_eq!(names.len(), 12);
    }
}
