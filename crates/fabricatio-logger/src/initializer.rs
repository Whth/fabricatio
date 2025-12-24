//! A loguru-inspired structured logging implementation for Fabricatio ecosystem
//!
//! Provides highly customizable logging with:
//! - Rich ANSI color output formatting
//! - Python/Rust interoperability through PyO3 bindings
//! - Automatic log level configuration
//! - Structured key-value logging via tracing subsystem
//!
//! # Features
//! - Loguru-style formatting with module/line context
//! - Cross-language configuration (read settings from Python)
//! - Custom log levels (SUCCESS/CRITICAL) through metadata filtering
//! - Thread-safe initialization and global logger management
//! - Precise timestamps using chrono's local timezone
//!
//! # Usage
//!
//! ## Basic Rust Initialization
//! ```rust
//! use fabricatio_logger::{init_logger, init_logger_auto};
//!
//! // Manual initialization with specified level
//! init_logger("debug",None,None)?;
//!
//! // Or automatic configuration from Python settings
//! init_logger_auto().expect("Failed to initialize logger from Python config");
//! ```
//!
//! # Implementation Details
//! Built on top of [`tracing`] ecosystem with custom [`FormatEvent`] implementation.
//! The logger propagates spans and events through the [`tracing_subscriber`] layer system.
//!
//! # Panics
//! - Will panic if initialization is attempted multiple times
//! - May panic on invalid UTF-8 in log messages
//!
//! [`tracing`]: https://docs.rs/tracing
//! [`FormatEvent`]: tracing_subscriber::fmt::FormatEvent
//! [`tracing_subscriber`]: https://docs.rs/tracing-subscriber

use fabricatio_constants::CONFIG_VARNAME;
use fabricatio_constants::CORE_PACKAGE_NAME;
use pyo3::prelude::*;
use std::io;
use std::path::PathBuf;
use std::str::FromStr;
use tracing_subscriber::prelude::*;
use tracing_subscriber::{fmt, EnvFilter};

use error_mapping::AsPyErr;

use crate::renderer::MyFormatter;
use strum::EnumString;
use tracing_appender::rolling::{daily, hourly, minutely, never};

#[derive(Default, EnumString)]
#[strum(serialize_all = "lowercase")]
pub enum RotationType {
    #[default]
    Never,
    Minutely,
    Hourly,
    Daily,
}

pub fn init_logger(level: &str, log_dir: Option<PathBuf>, rotation: Option<RotationType>) -> () {
    if let Some(sink) = log_dir {
        let name = format!("{}.log", env!("CARGO_CRATE_NAME"));
        let writer = match rotation.unwrap_or_default() {
            RotationType::Never => never(sink, name),
            RotationType::Minutely => minutely(sink, name),
            RotationType::Hourly => hourly(sink, name),
            RotationType::Daily => daily(sink, name),
        };
        let fmt_layer = fmt::layer()
            .with_target(true)
            .event_format(MyFormatter)
            .with_writer(writer)
            .with_filter(EnvFilter::new(level));

        tracing_subscriber::registry().with(fmt_layer).init();
    } else {
        let fmt_layer = fmt::layer()
            .with_target(true)
            .event_format(MyFormatter)
            .with_writer(io::stderr)
            .with_filter(EnvFilter::new(level));
        tracing_subscriber::registry().with(fmt_layer).init();
    };
}

pub fn init_logger_auto() -> PyResult<()> {
    let (level, sink, rotation) = Python::attach(|py| {
        let debug_config = py
            .import(CORE_PACKAGE_NAME)?
            .getattr(CONFIG_VARNAME)?
            .getattr("debug")?;

        Ok((
            debug_config
                .getattr("log_level")?
                .extract::<String>()
                .into_pyresult()?,
            debug_config
                .getattr("log_dir")?
                .extract::<Option<PathBuf>>()
                .into_pyresult()?,
            debug_config
                .getattr("rotation")?
                .extract::<Option<String>>()
                .into_pyresult()?,
        ))
    })?;

    init_logger(
        level.as_str(),
        sink,
        rotation.map(|s| s.parse::<RotationType>().unwrap_or_default()),
    );
    Ok(())
}
