use crate::linter;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::collections::HashSet;

/// Represents the mode of checking, either a whitelist or a blacklist.
#[derive(Clone, Debug)]
enum CheckMode {
    WhiteList,
    BlackList,
}

const WHITELIST: &str = "whitelist";
const BLACKLIST: &str = "blacklist";

/// Configuration for checks, specifying the mode and target items.
#[pyclass]
#[derive(Debug, Clone)]
struct CheckConfig {
    mode: CheckMode,
    targets: HashSet<String>,
}

#[pymethods]
impl CheckConfig {
    /// Create a new CheckConfig instance with specified targets and mode.
    #[new]
    fn new(targets: HashSet<String>, mode: String) -> PyResult<Self> {
        let mode_enum = match mode.as_str() {
            WHITELIST => Ok(CheckMode::WhiteList),
            BLACKLIST => Ok(CheckMode::BlackList),
            _ => Err(PyRuntimeError::new_err(format!(
                "Invalid mode: {}, Must be one of {} or {}",
                mode, WHITELIST, BLACKLIST
            ))),
        };

        Ok(Self {
            mode: mode_enum?,
            targets,
        })
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
        config = match modules.mode {
            CheckMode::WhiteList => config.with_allowed_modules(modules.targets),
            CheckMode::BlackList => config.with_forbidden_modules(modules.targets),
        }
    };

    if let Some(imports) = imports {
        config = match imports.mode {
            CheckMode::WhiteList => config.with_allowed_imports(imports.targets),
            CheckMode::BlackList => config.with_forbidden_imports(imports.targets),
        }
    };

    if let Some(calls) = calls {
        config = match calls.mode {
            CheckMode::WhiteList => config.with_allowed_calls(calls.targets),
            CheckMode::BlackList => config.with_forbidden_calls(calls.targets),
        }
    };

    linter::gather_violations(source, config).map_err(|err| PyRuntimeError::new_err(err))
}

/// Registers the gather_violations function with the Python module.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(gather_violations, m)?)?;
    Ok(())
}
