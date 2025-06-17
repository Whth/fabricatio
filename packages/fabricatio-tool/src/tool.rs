use crate::linter;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::collections::HashSet;

const WHITELIST: &str = "whitelist";
const BLACKLIST: &str = "blacklist";

/// Configuration for checks, specifying the mode and target items.
#[pyclass]
#[derive(Debug, Clone)]
struct CheckConfig {
    mode: String,
    targets: HashSet<String>,
}

#[pymethods]
impl CheckConfig {
    /// Create a new CheckConfig instance with specified targets and mode.
    #[new]
    #[pyo3(signature = (targets, mode=WHITELIST.to_string()))]
    fn new(targets: HashSet<String>, mode: String) -> PyResult<Self> {
        if mode != WHITELIST && mode != BLACKLIST {
            return Err(PyRuntimeError::new_err(format!(
                "Invalid mode: {}, Must be one of {} or {}",
                mode, WHITELIST, BLACKLIST
            )));
        }

        Ok(Self { mode, targets })
    }
}

/// Gathers violations in the provided source code based on the given configuration.
#[pyfunction]
#[pyo3(signature = (source, modules=None, imports=None, calls=None))]
fn gather_violations(
    source: &str,
    modules: Option<CheckConfig>,
    imports: Option<CheckConfig>,
    calls: Option<CheckConfig>,
) -> PyResult<Vec<String>> {
    let mut config = linter::LinterConfig::new();
    if let Some(modules) = modules {
        if modules.mode == WHITELIST {
            config = config.with_allowed_modules(modules.targets);
        } else if modules.mode == BLACKLIST {
            config = config.with_forbidden_modules(modules.targets);
        }
    };

    if let Some(imports) = imports {
        if imports.mode == WHITELIST {
            config = config.with_allowed_imports(imports.targets);
        } else if imports.mode == BLACKLIST {
            config = config.with_forbidden_imports(imports.targets);
        }
    };

    if let Some(calls) = calls {
        if calls.mode == WHITELIST {
            config = config.with_allowed_calls(calls.targets);
        } else if calls.mode == BLACKLIST {
            config = config.with_forbidden_calls(calls.targets);
        }
    };

    linter::gather_violations(source, config).map_err(|err| PyRuntimeError::new_err(err))
}

/// Registers the gather_violations function with the Python module.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(gather_violations, m)?)?;
    m.add_class::<CheckConfig>()?;
    Ok(())
}
