use once_cell::sync::Lazy;
use pyo3::prelude::*;
#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;
use scanner::PythonPackageScanner;

/// A static scanner instance used to check Python package installations and extras.
static SCANNER: Lazy<PythonPackageScanner> = Lazy::new(PythonPackageScanner::default);

/// Checks if a Python package is installed.
///
/// Args:
///     pkg_name: The name of the package to check.
///
/// Returns:
///     True if the package is installed, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn is_installed(pkg_name: &str) -> bool {
    SCANNER.is_installed(pkg_name)
}

/// Lists all installed Python packages.
///
/// Returns:
///     A list of names of all installed packages.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn list_installed() -> Vec<String> {
    SCANNER.list_installed()
}

/// Checks if a specific extra (optional dependency) of a Python package is satisfied.
///
/// Args:
///     pkg_name: The name of the package.
///     extra_name: The name of the extra/optional dependency.
///
/// Returns:
///     True if the extra is satisfied, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn extra_satisfied(pkg_name: &str, extra_name: &str) -> bool {
    SCANNER.extra_satisfied(pkg_name, extra_name)
}

/// Checks if all specified extras (optional dependencies) of a Python package are satisfied.
///
/// Args:
///     pkg_name: The name of the package.
///     extras: A list of extra/optional dependency names to check.
///
/// Returns:
///     True if all extras are satisfied, False otherwise.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
pub fn extras_satisfied(pkg_name: &str, extras: Vec<String>) -> bool {
    SCANNER.extras_satisfied(pkg_name, extras)
}

/// Registers the Python package scanning functions with the module.
///
/// Args:
///     _: The Python interpreter instance.
///     m: The Python module to register with.
///
/// Returns:
///     PyResult<()> indicating success.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(is_installed, m)?)?;
    m.add_function(wrap_pyfunction!(list_installed, m)?)?;
    m.add_function(wrap_pyfunction!(extra_satisfied, m)?)?;
    m.add_function(wrap_pyfunction!(extras_satisfied, m)?)?;
    Ok(())
}
