use chrono::{DateTime, Local};
use fabricatio_constants::PY_SOURCE_KEY;
use tracing::field::{Field, Visit};
use tracing::{Event, Subscriber};
use tracing_subscriber::fmt::{FmtContext, FormatEvent, FormatFields, format};
use tracing_subscriber::registry::LookupSpan;

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
pub struct MyFormatter;

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
        let mut visitor = PySourceVisitor {
            py_source_value: None,
            message: None,
        };
        event.record(&mut visitor);

        let meta = event.metadata();

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
