use std::time::SystemTime;
use tracing_subscriber::fmt::time::FormatTime;
use tracing_subscriber::prelude::*;
use tracing_subscriber::{EnvFilter, fmt};

/// A custom time formatter that formats time in HH:MM:SS format.
struct LoguruTime;

impl FormatTime for LoguruTime {
    /// Formats the current time as HH:MM:SS.
    ///
    /// # Arguments
    ///
    /// * `w` - A mutable reference to the writer to which the formatted time is written.
    ///
    /// # Returns
    ///
    /// A `std::fmt::Result` indicating the result of the write operation.
    fn format_time(&self, w: &mut fmt::format::Writer<'_>) -> std::fmt::Result {
        let now = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .expect("Time went backwards");
        let secs = now.as_secs() % 86400; // 只保留一天内的秒数
        let hours = (secs / 3600) as u32;
        let minutes = (secs % 3600) / 60;
        let seconds = (secs % 60) as u32;

        write!(w, "{:02}:{:02}:{:02}", hours, minutes, seconds)
    }
}

/// Initializes the logger with a custom time format and default logging settings.
///
/// The logger is configured with:
/// - Environment-based filtering (falls back to info level, with debug for this crate)
/// - Custom time formatting (HH:MM:SS)
/// - Level, target, and line number information in logs
/// - Compact formatting
pub(crate) fn init_logger(level: &str) {
    tracing_subscriber::registry()
        .with(EnvFilter::new(format!(
            "{level},SUCCESS=info,CRITICAL=error"
        )))
        .with(
            fmt::layer().event_format(
                fmt::format()
                    .with_timer(LoguruTime)
                    .with_level(true)
                    .with_target(true)
                    .with_file(false) // 如果你不需要文件名
                    .with_line_number(true)
                    .compact(),
            ),
        )
        .init();
}
