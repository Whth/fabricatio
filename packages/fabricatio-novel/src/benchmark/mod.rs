//! The measures a benchmark scorecard is built from.
//!
//! A measure is a named reading of prose. It carries its own [`Knobs`] — and, where the reading
//! needs one, its own input, such as the probe table a run is checked against — and it implements
//! [`Measure`]: given any corpus of borrowed texts in reading order it answers with the evidence it
//! gathered. The evidence implements [`Reported`], which projects it into [`Metrics`]: a flat list
//! of `<measure>.<metric>` numbers.
//!
//! That list is what makes the benchmark extensible. A measure is a new type, a new `impl Measure`
//! and one line in [`register`]; every number it reports reaches a scorecard the moment it is
//! reported, and its evidence — the pairs, seams, tallies and counts a number was derived from —
//! travels with it, so a number can always be read back to the readings behind it. Every size a
//! measure reads a run by lives in one place, [`Knobs`], so the same run can be scored another way
//! without touching this crate.

mod knobs;
mod probes;
mod repetition;
mod script;
mod vocabulary;

use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

pub(crate) use knobs::Knobs;

/// One number a measure reported, named the way a report prints it: `<measure>.<metric>`.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(frozen, skip_from_py_object)]
#[derive(Clone, Debug, PartialEq)]
pub struct Metric {
    /// The metric's name: the measure it came from, a dot, and the number it counts.
    #[pyo3(get)]
    name: String,

    /// The number.
    #[pyo3(get)]
    value: f64,
}

impl Metric {
    /// The number `metric` of `measure`.
    fn of(measure: &str, metric: &str, value: f64) -> Self {
        Self {
            name: format!("{measure}.{metric}"),
            value,
        }
    }
}

/// Every number a measure reported, in the order it reported them.
pub(crate) type Metrics = Vec<Metric>;

/// A named measure of prose.
///
/// `T` is the text the measure reads — anything borrowing as `str` — and a corpus is any iterator
/// of borrowed texts, so one measure reads a whole manuscript, a run's scenes in reading order, or
/// any other sequence that means something for the reading it does.
pub(crate) trait Measure<T>
where
    T: AsRef<str> + ?Sized,
{
    /// The evidence: the readings the numbers were derived from, kept so a report can show them.
    type Evidence: Reported;

    /// Reads a corpus, in reading order.
    fn measure<'a, C>(&self, corpus: C) -> Self::Evidence
    where
        C: IntoIterator<Item = &'a T>,
        T: 'a;
}

/// The numbers behind a measure's evidence.
pub(crate) trait Reported {
    /// The measure the evidence came from: the prefix of every metric name it reports.
    const MEASURE: &'static str;

    /// Every number this evidence reports, named `<measure>.<metric>`, in a fixed order.
    fn metrics(&self) -> Metrics;
}

/// The numbers `measure` reports, as the `(metric, value)` pairs it hands out.
fn report<'a>(measure: &str, numbers: impl IntoIterator<Item = (&'a str, f64)>) -> Metrics {
    numbers
        .into_iter()
        .map(|(metric, value)| Metric::of(measure, metric, value))
        .collect()
}

/// The share one count is of another, `0.0` when the whole is empty.
fn share(part: usize, whole: usize) -> f64 {
    if whole == 0 {
        0.0
    } else {
        part as f64 / whole as f64
    }
}

/// Registers the benchmark surface with the Python module: the framework's types, then one entry
/// point per measure.
pub(crate) fn register(python: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Knobs>()?;
    m.add_class::<Metric>()?;
    repetition::register(python, m)?;
    vocabulary::register(python, m)?;
    probes::register(python, m)?;
    script::register(python, m)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::collections::HashSet;

    use super::probes::Probes;
    use super::repetition::Repetition;
    use super::script::Script;
    use super::vocabulary::Vocabulary;
    use super::*;

    /// One measure's report, named by the measure itself, over one corpus.
    fn named<T, M>(measure: &M, corpus: &[T]) -> (&'static str, Metrics)
    where
        T: AsRef<str>,
        M: Measure<T>,
    {
        (
            M::Evidence::MEASURE,
            measure.measure(corpus.iter()).metrics(),
        )
    }

    /// Every measure, read over the same corpus, as `(name, metrics)`.
    fn measured() -> Vec<(&'static str, Metrics)> {
        let knobs = Knobs::default();
        let corpus = [
            "the keeper rows out to the rocks. the keeper rows back again.",
            "",
        ];
        vec![
            named(&Repetition::new(knobs), &corpus),
            named(&Vocabulary::new(knobs), &corpus),
            named(&Script, &corpus),
            named(
                &Probes::new(
                    vec!["keeper".to_string()],
                    vec!["rocks".to_string()],
                    vec![vec!["rows".to_string(), "rowed".to_string()]],
                    HashSet::new(),
                ),
                &corpus,
            ),
        ]
    }

    #[test]
    fn prefixes_every_reported_metric_with_the_measure_that_reported_it() {
        for (measure, metrics) in measured() {
            assert!(!metrics.is_empty(), "{measure} reported nothing");
            for metric in &metrics {
                assert!(
                    metric.name.starts_with(&format!("{measure}.")),
                    "{} is not reported under {measure}",
                    metric.name
                );
            }
        }
    }

    #[test]
    fn names_every_reported_metric_once() {
        let names: Vec<String> = measured()
            .into_iter()
            .flat_map(|(_, metrics)| metrics.into_iter().map(|metric| metric.name))
            .collect();
        let distinct: HashSet<&String> = names.iter().collect();
        assert_eq!(
            names.len(),
            distinct.len(),
            "two measures reported one name"
        );
    }

    #[test]
    fn shares_a_count_of_nothing_as_nothing() {
        assert_eq!(share(3, 0), 0.0);
        assert_eq!(share(3, 6), 0.5);
    }
}
