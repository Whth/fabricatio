//! Which probe terms a run's prose uses.

use std::collections::HashSet;

use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

use super::{Measure, Metrics, Reported, report};

/// The evidence a probe reading leaves behind: what every term of the table measured.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(frozen, get_all)]
pub struct ProbeReport {
    /// How many characters the prose holds, whitespace included.
    chars: usize,

    /// The watch terms the prose uses, in table order, with their counts.
    watch: Vec<(String, u32)>,

    /// The gated terms the prose uses, in table order, with their counts.
    gated: Vec<(String, u32)>,

    /// Per alias group, in table order, the variants the prose uses, with their counts.
    aliases: Vec<Vec<(String, u32)>>,

    /// How many alias groups the prose uses two or more variants of.
    ///
    /// Those are the mixes a reader notices; one variant of a group is the name the run settled on.
    mixed_groups: usize,

    /// The watch terms the licensed vocabulary leaves out, with their counts.
    unlicensed: Vec<(String, u32)>,

    /// How many of the prose's 1000 characters the watch terms make up.
    watch_per_1k: f64,
}

impl ProbeReport {
    /// Read one run of prose against a probe table.
    fn of(
        chars: usize,
        watch: Vec<(String, u32)>,
        gated: Vec<(String, u32)>,
        aliases: Vec<Vec<(String, u32)>>,
        licensed: &HashSet<String>,
    ) -> Self {
        let hits = Self::total(&watch);
        Self {
            mixed_groups: aliases.iter().filter(|group| group.len() > 1).count(),
            unlicensed: watch
                .iter()
                .filter(|(term, _)| !licensed.contains(term))
                .cloned()
                .collect(),
            watch_per_1k: if chars == 0 {
                0.0
            } else {
                f64::from(hits) / chars as f64 * 1000.0
            },
            chars,
            watch,
            gated,
            aliases,
        }
    }

    /// How often the watch terms occur.
    fn watch_total(&self) -> u32 {
        Self::total(&self.watch)
    }

    /// How often the gated terms occur.
    fn gated_total(&self) -> u32 {
        Self::total(&self.gated)
    }

    /// How often the watch terms no plan text licenses occur.
    fn unlicensed_total(&self) -> u32 {
        Self::total(&self.unlicensed)
    }

    /// How often the counted terms occur in all.
    fn total(counted: &[(String, u32)]) -> u32 {
        counted.iter().map(|(_, count)| *count).sum()
    }
}

impl Reported for ProbeReport {
    const MEASURE: &'static str = "probes";

    fn metrics(&self) -> Metrics {
        report(
            Self::MEASURE,
            [
                ("chars", self.chars as f64),
                ("watch_terms", self.watch.len() as f64),
                ("watch_total", f64::from(self.watch_total())),
                ("watch_per_1k", self.watch_per_1k),
                ("gated_terms", self.gated.len() as f64),
                ("gated_total", f64::from(self.gated_total())),
                ("alias_groups", self.aliases.len() as f64),
                ("mixed_groups", self.mixed_groups as f64),
                ("unlicensed_terms", self.unlicensed.len() as f64),
                ("unlicensed_total", f64::from(self.unlicensed_total())),
            ],
        )
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl ProbeReport {
    /// Every number this reading reported, named `probes.<metric>`.
    fn metrics(&self) -> Metrics {
        <Self as Reported>::metrics(self)
    }
}

/// What a run's prose makes of a probe table.
///
/// The table is the measure's own input: the terms to count, and the vocabulary a plan text uses
/// itself, without which a watch hit is a term the run invented.
pub(crate) struct Probes {
    /// The terms whose presence is reported.
    watch: Vec<String>,

    /// The terms whose presence fails the run.
    gated: Vec<String>,

    /// The variant groups the run should settle on one name for.
    aliases: Vec<Vec<String>>,

    /// The vocabulary the plan text uses itself.
    licensed: HashSet<String>,
}

impl Probes {
    /// The measure, reading against one table.
    pub(super) fn new(
        watch: Vec<String>,
        gated: Vec<String>,
        aliases: Vec<Vec<String>>,
        licensed: HashSet<String>,
    ) -> Self {
        Self {
            watch,
            gated,
            aliases,
            licensed,
        }
    }

    /// The terms of one group the prose uses, in the group's order, each with its count over the
    /// whole corpus: a term is reported once, however many documents use it.
    fn used<'a>(prose: &[&str], terms: impl IntoIterator<Item = &'a String>) -> Vec<(String, u32)> {
        terms
            .into_iter()
            .filter_map(|term| {
                let count = prose
                    .iter()
                    .map(|document| Self::count(document, term))
                    .sum::<u32>();
                (count > 0).then(|| (term.clone(), count))
            })
            .collect()
    }

    /// How often one term occurs in one document.
    ///
    /// Counted the way `str.count` counts: left to right and never overlapping itself, and an empty
    /// term at every position of the text plus one. The needle is matched as bytes, which finds the
    /// same occurrences as matching characters would — a valid UTF-8 needle can only align on the
    /// character boundaries of a valid UTF-8 text.
    fn count(document: &str, term: &str) -> u32 {
        if term.is_empty() {
            return document.chars().count() as u32 + 1;
        }
        memchr::memmem::find_iter(document.as_bytes(), term.as_bytes()).count() as u32
    }
}

impl<T> Measure<T> for Probes
where
    T: AsRef<str> + ?Sized,
{
    type Evidence = ProbeReport;

    fn measure<'a, C>(&self, corpus: C) -> ProbeReport
    where
        C: IntoIterator<Item = &'a T>,
        T: 'a,
    {
        let prose: Vec<&str> = corpus.into_iter().map(AsRef::as_ref).collect();
        ProbeReport::of(
            prose.iter().flat_map(|document| document.chars()).count(),
            Self::used(&prose, &self.watch),
            Self::used(&prose, &self.gated),
            self.aliases
                .iter()
                .map(|group| Self::used(&prose, group))
                .collect(),
            &self.licensed,
        )
    }
}

/// Counts what a run's prose makes of a probe table.
///
/// Every term of the table is counted over the prose: the watch terms, the gated ones, and the
/// variants of every alias group. The terms a plan text uses itself are handed in as `licensed`, so
/// the report tells the run's own vocabulary from the table's.
///
/// Args:
///     text: The prose to read.
///     watch: The terms whose presence is reported, in table order.
///     gated: The terms whose presence fails the run, in table order.
///     aliases: The variant groups, each in table order.
///     licensed: The vocabulary the plan text uses itself.
///
/// Returns:
///     The counts of every term the prose uses, and the numbers summarising them.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
#[pyo3(signature = (text, watch, gated, aliases, licensed))]
fn measure_probes(
    text: &str,
    watch: Vec<String>,
    gated: Vec<String>,
    aliases: Vec<Vec<String>>,
    licensed: HashSet<String>,
) -> ProbeReport {
    Probes::new(watch, gated, aliases, licensed).measure(std::iter::once(text))
}

/// Registers the probe measure with the Python module.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<ProbeReport>()?;
    m.add_function(wrap_pyfunction!(measure_probes, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn table() -> Probes {
        Probes::new(
            vec!["silver".to_string(), "locket".to_string()],
            vec!["mustard".to_string()],
            vec![
                vec!["row".to_string(), "rowed".to_string()],
                vec!["boat".to_string(), "ship".to_string()],
            ],
            HashSet::from(["row".to_string()]),
        )
    }

    #[test]
    fn counts_the_occurrences_of_every_term_it_lists() {
        // A term counts inside a longer word, the way `str.count` reads it: "row" occurs in "rowed".
        let report = table().measure(["the row rowed past the silver locket"]);
        assert_eq!(
            report.watch,
            vec![("silver".to_string(), 1), ("locket".to_string(), 1)]
        );
        assert_eq!(report.gated, vec![]);
        assert_eq!(
            report.aliases,
            vec![
                vec![("row".to_string(), 2), ("rowed".to_string(), 1)],
                vec![],
            ]
        );
        assert_eq!(report.mixed_groups, 1);
    }

    #[test]
    fn leaves_out_the_terms_the_prose_never_uses() {
        let report = table().measure(["the lantern hums"]);
        assert!(report.watch.is_empty());
        assert!(report.gated.is_empty());
        assert_eq!(report.aliases, vec![vec![], vec![]]);
        assert_eq!(report.mixed_groups, 0);
        assert_eq!(report.watch_total(), 0);
        assert_eq!(report.watch_per_1k, 0.0);
    }

    #[test]
    fn counts_a_term_once_per_non_overlapping_occurrence() {
        // "aaa" holds one non-overlapping "aa", the way `str.count` reads it.
        let report = Probes::new(vec!["aa".to_string()], vec![], vec![], HashSet::new())
            .measure(["aaa aaa"]);
        assert_eq!(report.watch, vec![("aa".to_string(), 2)]);
    }

    #[test]
    fn counts_the_watch_rate_over_every_character_of_the_prose() {
        let report = table().measure(["silver"]);
        assert_eq!(report.chars, 6);
        assert_eq!(report.watch_total(), 1);
        assert_eq!(report.watch_per_1k, 1000.0 / 6.0);
    }

    #[test]
    fn names_the_watch_terms_no_plan_text_licenses() {
        let report = table().measure(["the row past the silver locket"]);
        assert_eq!(
            report.unlicensed,
            vec![("silver".to_string(), 1), ("locket".to_string(), 1)]
        );
        assert_eq!(report.unlicensed_total(), 2);
    }

    #[test]
    fn adds_up_the_counts_of_every_document_it_reads() {
        let report = table().measure(["silver", "silver locket"]);
        assert_eq!(report.chars, 19);
        assert_eq!(
            report.watch,
            vec![("silver".to_string(), 2), ("locket".to_string(), 1)]
        );
    }
}
