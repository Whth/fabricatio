use std::collections::HashSet;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use crate::linter;

#[pyfunction]
fn gather_violations(source: &str, forbidden_modules: HashSet<String>, forbidden_imports: HashSet<String>, forbidden_calls: HashSet<String>)-> PyResult<Vec<String>> {
    let config = linter::LinterConfig::new()
        .with_forbidden_modules(forbidden_modules)
        .with_forbidden_imports(forbidden_imports)
        .with_forbidden_calls(forbidden_calls);
    linter::gather_violations(source, config).map_err(|err| PyRuntimeError::new_err(err))
 }


pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    
    m.add_function(wrap_pyfunction!(gather_violations, m)?)?;
    Ok(())
}