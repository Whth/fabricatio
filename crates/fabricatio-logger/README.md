# Fabricatio Logger

A comprehensive logging crate for the Fabricatio ecosystem, featuring loguru-inspired structured logging with rich ANSI
color output and seamless Python/Rust interoperability through PyO3 bindings.

## Overview

This crate provides highly customizable logging capabilities built on top of the `tracing` ecosystem with custom
formatting. It offers loguru-style formatting with module/line context, cross-language configuration, and thread-safe
initialization for the entire Fabricatio project.

## Features

### 🚀 Loguru-Style Formatting

- Rich ANSI color output for better readability
- Module and line context tracking
- Structured key-value logging via tracing subsystem
- Custom log levels (TRACE, DEBUG, INFO, WARN, ERROR) through metadata filtering

### 🔗 Python/Rust Integration

- Automatic log level configuration from Python settings
- Seamless PyO3 bindings for cross-language usage
- Source tracking for Python calls in Rust logging

### ⚙️ Advanced Configuration

- Automatic log rotation (never, minutely, hourly, daily)
- Thread-safe initialization and global logger management
- Precise timestamps using chrono's local timezone
- Configurable output destinations (stderr or file)

## Usage

### Basic Rust Usage

```rust
use fabricatio_logger::{init_logger, init_logger_auto, info, debug, warn, error};

fn main() {

    // Manual initialization with specified level
    init_logger("debug", None, None);

    // Or automatic configuration from Python settings
    init_logger_auto().expect("Failed to initialize logger from Python config");

    // Use the logging macros
    info!("Application started successfully");
    debug!("Debug information: {:?}", some_data);
    warn!("Warning: something might be wrong");
    error!("Error occurred: {}", error_message);
}
```

### Python Integration

The logger can be initialized from Python configuration and used from both Rust and Python:

```python
# Python side
from fabricatio_core import logger

# Initialize logger automatically from config
logger.info("Message from Python")
```

### Log Output Format

```
14:30:45 | INFO   | mymodule::function - Application started successfully
14:30:46 | DEBUG  | mymodule::process_data - Processing data: {"key": "value"}
14:30:47 | WARN   | mymodule::validate - Warning: invalid input detected
14:30:48 | ERROR  | mymodule::handle_error - Error occurred: connection failed
```

### Configuration

The logger supports configuration through Python's debug settings:

```python
# In your Python configuration
CONFIG = {
    "debug": {
        "log_level": "INFO",  # TRACE, DEBUG, INFO, WARN, ERROR
        "log_dir": "/path/to/logs",  # Optional log directory
        "rotation": "daily",  # never, minutely, hourly, daily
    }
}
```

## Log Levels

- **TRACE**: Very detailed diagnostic information
- **DEBUG**: Detailed information for debugging
- **INFO**: General informational messages
- **WARN**: Warning messages about potential issues
- **ERROR**: Error messages for recoverable failures

## Architecture

Built on top of the [`tracing`](https://docs.rs/tracing) ecosystem with custom [
`FormatEvent`](https://docs.rs/tracing-subscriber/latest/tracing_subscriber/fmt/trait.FormatEvent.html) implementation.
The logger propagates spans and events through the [`tracing_subscriber`](https://docs.rs/tracing-subscriber) layer
system.

## Dependencies

- `tracing`: Core tracing framework
- `tracing-subscriber`: Subscriber implementations for logging
- `tracing-appender`: File appending capabilities
- `chrono`: Timestamp handling with timezone support
- `pyo3`: Python bindings for cross-language integration
- `pyo3-stub-gen`: Python stub generation
- `strum`: Enum string conversion
- `fabricatio-constants`: Application constants and paths

## Examples

See the `examples` directory for complete usage examples demonstrating both Rust-only and cross-language scenarios.

## License

This crate is part of the Fabricatio project and follows the same licensing terms.