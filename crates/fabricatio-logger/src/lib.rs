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
//! init_logger("debug");
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

mod logger;

use crate::logger::PY_SOURCE_KEY;
use chrono::{DateTime, Local};
use fabricatio_config::CONFIG_VARNAME;
use fabricatio_constants::NAME;
pub use logger::Logger;
use pyo3::exceptions::PyModuleNotFoundError;
use pyo3::prelude::*;
use tracing::field::{Field, Visit};
use tracing::{Event, Subscriber};
use tracing_log::NormalizeEvent;
use tracing_subscriber::fmt::{FmtContext, FormatEvent, FormatFields, format};
use tracing_subscriber::prelude::*;
use tracing_subscriber::registry::LookupSpan;
use tracing_subscriber::{EnvFilter, fmt};

struct PySourceVisitor {
    py_source_value: Option<String>,
    message: Option<String>,
}

impl Visit for PySourceVisitor {
    fn record_debug(&mut self, field: &Field, value: &dyn std::fmt::Debug) {
        match field.name() {
            PY_SOURCE_KEY => {
                self.py_source_value = Some(format!("{:?}", value).replace("\"", ""));
            }
            "message" => {
                self.message = Some(format!("{:?}", value));
            }
            _ => {}
        }
    }
}

/// Custom event formatter that mimics loguru-style output.
/// Format: "HH:MM:SS | LEVEL   | target:span - message"
struct MyFormatter;

impl<S, N> FormatEvent<S, N> for MyFormatter
where
    S: Subscriber + for<'a> LookupSpan<'a>,
    N: for<'a> FormatFields<'a> + 'static,
{
    fn format_event(
        &self,
        _ctx: &FmtContext<'_, S, N>,
        mut writer: format::Writer<'_>,
        event: &Event<'_>,
    ) -> std::fmt::Result {
        let normalized_meta = event.normalized_metadata();

        let mut visitor = PySourceVisitor {
            py_source_value: None,
            message: None,
        };
        event.record(&mut visitor);

        let meta = normalized_meta.as_ref().unwrap_or_else(|| event.metadata());

        let level = event.metadata().level();

        let level_color: &str = match *level {
            tracing::Level::ERROR => "\x1b[31m\x1b[1m",
            tracing::Level::WARN => "\x1b[33m\x1b[1m",
            tracing::Level::INFO => "\x1b[0m\x1b[1m",
            tracing::Level::DEBUG => "\x1b[34m\x1b[1m",
            tracing::Level::TRACE => "\x1b[2m\x1b[1m",
        };

        // 1. Time (dimmed green)
        let local: DateTime<Local> = Local::now();
        let time = local.format("%H:%M:%S").to_string();
        let time = format!("{}{}{}", "\x1b[32m", time, "\x1b[0m");

        // 3. Target (cyan)
        let formatted_target = if let Some(py_source) = visitor.py_source_value {
            py_source
        } else {
            meta.target()
                .split_once("::")
                .map(|(before, after)| format!("{}::<rust>::{}", before, after))
                .unwrap_or_else(|| meta.target().to_string())
        };
        let formatted_target = format!("{}{}{}", "\x1b[36m", formatted_target, "\x1b[0m");
        // 4. Write formatted parts
        write!(
            writer,
            "{} \x1b[31m| {}{:<5}\x1b[0m \x1b[31m| {} \x1b[31m- ",
            time,
            level_color,
            level.as_str(),
            formatted_target
        )?;

        write!(
            writer,
            "{}{}\x1b[0m",
            level_color,
            visitor.message.unwrap_or_default()
        )?;
        writeln!(writer)
    }
}

/// Initializes the global logger with loguru-like formatting.
///
/// This configures:
/// - Environment filter for dynamic log levels
/// - Custom time format (HH:MM:SS)
/// - Compact, readable output with span context
/// - Support for custom "levels" like SUCCESS via target naming
///
/// # Arguments
///
/// * `level` - Default log level (e.g., "debug", "info")
///
/// # Example
///
/// ```
/// use fabricatio_logger::init_logger;
/// init_logger("debug");
/// ```
pub fn init_logger(level: &str) {
    let fmt_layer = fmt::layer().with_target(true).event_format(MyFormatter); // Use custom event format

    tracing_subscriber::registry()
        .with(EnvFilter::new(format!(
            "{},SUCCESS=info,CRITICAL=error",
            level
        )))
        .with(fmt_layer)
        .init();
}

pub fn init_logger_auto() -> PyResult<()> {
    let level = Python::with_gil(|py| {
        let mut n = NAME.to_string();
        n.push_str("_core");
        if let Ok(m) = py.import(n) {
            if let Ok(conf_obj) = m.getattr(CONFIG_VARNAME) {
                conf_obj
                    .getattr("debug")?
                    .getattr("log_level")?
                    .extract::<String>()
            } else {
                Err(PyModuleNotFoundError::new_err(
                    "CONFIG_VARNAME not found in module",
                ))
            }
        } else {
            Err(PyModuleNotFoundError::new_err("Config module not found"))
        }
    })?;
    init_logger(level.as_str());
    Ok(())
}

pub const LOGGER_VARNAME: &str = "logger";
