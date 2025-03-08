use biblatex::{Bibliography, ChunksExt};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use rayon::prelude::*;
use std::fs::File;
use std::io::Read;

#[pyclass]
pub struct BibManager {
    source:Bibliography,
}


#[pymethods]
impl BibManager {
    /// Create a new BibManager instance.
    #[new]
    fn new(path:String) -> PyResult<Self> {
        let mut bib=String::new();

        File::open(path)?.read_to_string(&mut bib).map_err(|e| PyErr::new::<PyRuntimeError,_>(format!("{}", e)))?;
        Ok(BibManager {
            source: Bibliography::parse(bib.as_str()).map_err(|e| PyErr::new::<PyRuntimeError,_>(format!("{}", e)))?,
        })
    }



    /// find the cite key of an article with given title
    fn get_cite_key(&self,title:String)->Option<String>{
        self.source.iter().par_bridge()
            .find_map_any(|entry|{
                if entry.title().map_err(|e| PyErr::new::<PyRuntimeError,_>(format!("{}", e))).ok()?.to_biblatex_string(false).to_lowercase()==title.to_lowercase(){
                    return Some(entry.key.clone())
                }
                None
            })
    }
}


pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<BibManager>()?;
    Ok(())
}