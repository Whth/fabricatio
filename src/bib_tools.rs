use biblatex::{Bibliography, ChunksExt};
use nucleo_matcher::pattern::{AtomKind, CaseMatching, Normalization, Pattern};
use nucleo_matcher::{Config, Matcher, Utf32Str};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use rayon::prelude::*;

#[pyclass]
pub struct BibManager {
    source: Bibliography,
}


#[pymethods]
impl BibManager {
    /// Create a new BibManager instance.
    #[new]
    fn new(path: String) -> PyResult<Self> {
        let bib = std::fs::read_to_string(path)
            .map_err(|e| PyErr::new::<PyRuntimeError, _>(e.to_string()))?;

        let source = Bibliography::parse(&bib)
            .map_err(|e| PyErr::new::<PyRuntimeError, _>(e.to_string()))?;

        Ok(BibManager { source })
    }

    /// find the cite key of an article with given title
    fn get_cite_key(&self, title: String) -> Option<String> {
        let title_lower = title.to_lowercase();

        self.source.iter().par_bridge()
            .find_map_any(|entry| {
                let entry_title = entry.title()
                    .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))
                    .ok()?
                    .to_biblatex_string(false)
                    .fix()
                    .to_lowercase();

                (entry_title == title_lower).then(|| entry.key.clone())
            })
    }

    /// Find the corresponding cite key of an article with given query string using fuzzy matcher
    fn get_cite_key_fuzzy(&self, query: String) -> Option<String> {
        let mut matcher = Matcher::new(Config::DEFAULT);
        let pattern = Pattern::new(
            query.as_str(),
            CaseMatching::Ignore,
            Normalization::Smart,
            AtomKind::Substring,
        );


        self.source.iter()
            .map(|entry| {
                let mut buf = vec![];
                let text = entry.to_biblatex_string().fix();
                (pattern.score(Utf32Str::new(text.as_str(), &mut buf), &mut matcher), entry)
            })
            .par_bridge()
            // Use filter_map's more concise form with pattern matching
            .filter_map(|(maybe_score, entry)| maybe_score.map(|score| (score, entry)))
            .max_by_key(|(score, _)| *score)
            .map(|(_, entry)| entry.key.clone())
    }
    #[pyo3(signature = (is_verbatim=false))]
    fn list_titles(&self, is_verbatim: bool) -> Vec<String> {
        self.source.iter().map(|entry| {
            entry.title()
                .map_err(|e| PyErr::new::<PyRuntimeError, _>(format!("{}", e)))
                .ok()
                .unwrap()
                .to_biblatex_string(is_verbatim)
                .fix()
        }).collect::<Vec<_>>()
    }

    fn get_author_by_key(&self, key: String)->Option<Vec<String>>{
        if let Some(en) = self.source.get(key.as_str()){
            Some(en.author().unwrap()
                .iter().map(
                |auther|{
                    format!("{}",auther).to_string()
                }
            ).collect())
            
        }else { 
            None
        }
    }
    
    
    
    fn get_year_by_key(&self, key: String)->Option<i32>{
        self.get_field_by_key(key, "year".to_string()).map(|s|{s.parse().unwrap()})
    }
    
    fn get_abstract_by_key(&self, key: String)->Option<String>{
        self.get_field_by_key(key, "abstract".to_string())
    }
    
    fn get_title_by_key(&self, key: String)->Option<String>{
        self.get_field_by_key(key, "title".to_string())
    }
    
    fn get_field_by_key(&self, key: String, field: String)->Option<String>{
        if let Some(en) = self.source.get(key.as_str()){
            Some(en.get(field.as_str()).unwrap().to_biblatex_string(false).fix())
        }else { 
            None
        }
    }

}

trait Fix{
    fn fix(&self)->String;
}

impl Fix for String {
    fn fix(&self) -> String {
        self.replace("{","").replace("}","")
    }
}




pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<BibManager>()?;
    Ok(())
}