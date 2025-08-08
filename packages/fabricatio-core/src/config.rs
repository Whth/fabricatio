use fabricatio_config::{CONFIG_VARNAME, Config, SecretStr};
use pyo3::prelude::*;

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<SecretStr>()?;
    m.add(CONFIG_VARNAME, Config::new()?)?;
    Ok(())
}
