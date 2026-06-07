use biblatex::{Bibliography, ChunksExt, PermissiveType};
use error_mapping::AsPyErr;
use nucleo_matcher::pattern::{AtomKind, CaseMatching, Normalization, Pattern};
use nucleo_matcher::{Config, Matcher, Utf32Str};
use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;
use rayon::prelude::*;

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass]
pub struct BibManager {
    source: Bibliography,
}

impl BibManager {
    /// Shared fuzzy search: finds the cite key whose `text_fn` output scores highest.
    fn best_fuzzy_match(
        &self,
        query: &str,
        text_fn: fn(&biblatex::Entry) -> Option<String>,
    ) -> Option<String> {
        let mut matcher = Matcher::new(Config::DEFAULT);
        let pattern = Pattern::new(
            query,
            CaseMatching::Ignore,
            Normalization::Smart,
            AtomKind::Fuzzy,
        );

        self.source
            .iter()
            .filter_map(|entry| {
                let mut buf = vec![];
                let text = text_fn(entry)?;
                let score = pattern.score(Utf32Str::new(text.as_str(), &mut buf), &mut matcher);
                Some((score?, entry))
            })
            .par_bridge()
            .max_by_key(|(score, _)| *score)
            .map(|(_, entry)| entry.key.clone())
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl BibManager {
    /// Create a new BibManager instance.
    #[new]
    fn new(path: String) -> PyResult<Self> {
        let bib = std::fs::read_to_string(path).into_pyresult()?;
        let source = Bibliography::parse(&bib).into_pyresult()?;
        Ok(BibManager { source })
    }

    /// find the cite key of an article with given title
    fn get_cite_key_by_title(&self, title: String) -> Option<String> {
        let title_lower = title.to_lowercase();

        self.source.iter().par_bridge().find_map_any(|entry| {
            let entry_title = entry
                .title()
                .ok()?
                .to_biblatex_string(false)
                .remove_brackets()
                .to_lowercase();

            (entry_title == title_lower).then(|| entry.key.clone())
        })
    }

    fn get_cite_key_by_title_fuzzy(&self, title: String) -> Option<String> {
        self.best_fuzzy_match(&title, |entry| {
            Some(
                entry
                    .title()
                    .ok()?
                    .to_biblatex_string(false)
                    .remove_brackets(),
            )
        })
    }

    /// Find the corresponding cite key of an article with given query string using fuzzy matcher
    fn get_cite_key_fuzzy(&self, query: String) -> Option<String> {
        self.best_fuzzy_match(&query, |entry| {
            Some(entry.to_biblatex_string().remove_brackets())
        })
    }

    #[pyo3(signature = (is_verbatim=false))]
    fn list_titles(&self, is_verbatim: bool) -> Vec<String> {
        self.source
            .iter()
            .filter_map(|entry| {
                Some(
                    entry
                        .title()
                        .ok()?
                        .to_biblatex_string(is_verbatim)
                        .remove_brackets(),
                )
            })
            .collect()
    }

    fn get_author_by_key(&self, key: &str) -> Option<Vec<String>> {
        self.source.get(key).map(|en| {
            en.author()
                .unwrap()
                .iter()
                .map(|author| author.to_string())
                .collect()
        })
    }

    fn get_year_by_key(&self, key: &str) -> Option<i32> {
        self.source.get(key).and_then(|en| match en.date().ok()? {
            PermissiveType::Typed(t) => match t.value {
                biblatex::DateValue::At(da)
                | biblatex::DateValue::Before(da)
                | biblatex::DateValue::After(da)
                | biblatex::DateValue::Between(da, _) => Some(da.year),
            },
            _ => None,
        })
    }

    fn get_abstract_by_key(&self, key: &str) -> Option<String> {
        self.get_field_by_key(key, "abstract")
    }

    fn get_title_by_key(&self, key: &str) -> Option<String> {
        self.get_field_by_key(key, "title")
    }

    fn get_field_by_key(&self, key: &str, field: &str) -> Option<String> {
        self.source
            .get(key)
            .and_then(|en| Some(en.get(field)?.to_biblatex_string(false).remove_brackets()))
    }
}

/// Remove curly braces from a string.
trait RemoveBrackets {
    fn remove_brackets(&self) -> String;
}

impl RemoveBrackets for str {
    fn remove_brackets(&self) -> String {
        self.replace('{', "").replace('}', "")
    }
}

impl RemoveBrackets for String {
    fn remove_brackets(&self) -> String {
        self.as_str().remove_brackets()
    }
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<BibManager>()?;
    Ok(())
}
