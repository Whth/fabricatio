//! # Fabricatio Config
//!
//! A comprehensive configuration management crate for the Fabricatio ecosystem, providing multi-source configuration loading with validation, Python integration, and secure handling of sensitive data.
//!
//! ## Features
//!
//! - **Multi-Source Configuration**: Environment variables, TOML files, pyproject.toml, and global config
//! - **Configuration Validation**: Comprehensive validation using the validator crate
//! - **Secure Data Handling**: SecretStr for sensitive data with automatic redaction
//! - **Python Integration**: Full PyO3 bindings and dynamic Python object creation
//!
//! ## Usage
//!
//! ```rust
//! use fabricatio_config::Config;
//! use pyo3::prelude::*;
//!
//! fn main() -> PyResult<()> {
//!     // Load configuration from all sources
//!     let config = Config::new()?;
//!
//!     // Access configuration sections
//!     println!("LLM Model: {:?}", config.llm.model);
//!     println!("Log Level: {:?}", config.debug.log_level);
//!
//!     Ok(())
//! }
//! ```
//!
//! For more information, see the [README](https://github.com/Whth/fabricatio/blob/main/crates/fabricatio-config/README.md).

mod config_loader;
mod configs;
mod secstr;

pub use crate::configs::*;
pub use crate::secstr::*;
