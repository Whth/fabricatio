# Fabricatio Config

A comprehensive configuration management crate for the Fabricatio ecosystem, providing multi-source configuration loading with validation, Python integration, and secure handling of sensitive data.

## Overview

This crate handles configuration management for the entire Fabricatio project, loading settings from multiple sources including environment variables, TOML files, and pyproject.toml with comprehensive validation and seamless Python interoperability.

## Features

### 📁 Multi-Source Configuration Loading
- **Environment Variables**: Prefixed environment variable support with `FABRICATIO_` prefix
- **TOML Files**: Configuration files (`fabricatio.toml`)
- **pyproject.toml**: Project configuration from standard Python project structure
- **Global Configuration**: User-wide configuration in platform-specific directories

### ✅ Configuration Validation
- **Field Validation**: Comprehensive validation using `validator` crate
- **Type Safety**: Strong typing for all configuration values
- **Range Checking**: Validation for numeric ranges and constraints
- **URL Validation**: Automatic validation of API endpoints

### 🔒 Secure Data Handling
- **SecretStr**: Secure storage for sensitive data like API keys
- **Redacted Output**: Automatic redaction in logs and debugging
- **Serialization Protection**: Safe serialization that doesn't expose secrets

### 🐍 Python Integration
- **PyO3 Bindings**: Full Python class generation with pyo3-stub-gen
- **Python Object Creation**: Dynamic Python object instantiation from config
- **Cross-Language Config**: Shared configuration between Rust and Python

## Configuration Structure

### Main Configuration Sections

```rust
Config {
    // LLM configuration with comprehensive settings
    llm: LLMConfig,
    
    // Embedding model configuration  
    embedding: EmbeddingConfig,
    
    // Debug and logging settings
    debug: DebugConfig,
    
    // Template management configuration
    templates: TemplateConfig,
    template_manager: TemplateManagerConfig,
    
    // Request routing and load balancing
    routing: RoutingConfig,
    
    // General application settings
    general: GeneralConfig,
    
    // Event emitter configuration
    emitter: EmitterConfig,
    
    // Extension configuration store
    ext: HashMap<String, Value>,
}
```

### LLM Configuration (LLMConfig)

```rust
LLMConfig {
    api_endpoint: Option<String>,          // Valid URL for API service
    api_key: Option<SecretStr>,            // Secure authentication token
    timeout: Option<u64>,                  // Minimum 1 second
    max_retries: Option<u32>,              // Minimum 1 retry
    model: Option<String>,                 // Model identifier
    temperature: Option<f32>,              // Range 0.0-2.0
    stop_sign: Option<Vec<String>>,        // Token generation stop sequences
    top_p: Option<f32>,                    // Nucleus sampling (0.0-1.0)
    stream: bool,                          // Streaming responses
    max_tokens: Option<u32>,               // Minimum 1 token
    // ... and more settings
}
```

## Usage

### Basic Rust Usage

```rust
use fabricatio_config::Config;
use pyo3::prelude::*;

fn main() -> PyResult<()> {
    // Load configuration from all sources
    let config = Config::new()?;
    
    // Access configuration sections
    println!("LLM Model: {:?}", config.llm.model);
    println!("Log Level: {:?}", config.debug.log_level);
    
    // Access template configuration
    println!("Task Briefing Template: {:?}", config.templates.task_briefing_template);
    
    Ok(())
}
```

### Python Integration

```python
from fabricatio_config import Config

# Load configuration
config = Config()

# Access configuration from Python
print(f"LLM Model: {config.llm.model}")
print(f"Log Level: {config.debug.log_level}")

# Use the load method for dynamic configuration
dynamic_config = config.load("my_section", MyPythonClass)
```

### Environment Variable Configuration

```bash
# Set configuration via environment variables
export FABRICATIO_LLM__API_ENDPOINT="https://api.openai.com"
export FABRICATIO_LLM__API_KEY="your-api-key-here"
export FABRICATIO_LLM__MODEL="gpt-4"
export FABRICATIO_DEBUG__LOG_LEVEL="DEBUG"
```

### TOML Configuration File

```toml
# fabricatio.toml
[llm]
api_endpoint = "https://api.openai.com"
api_key = "your-api-key-here"
model = "gpt-4"
temperature = 0.7
timeout = 30
max_retries = 3

[debug]
log_level = "INFO"
log_dir = "/var/log/fabricatio"
rotation = "daily"

[templates]
task_briefing_template = "task_briefing.hbs"
dependencies_template = "dependencies.hbs"
```

## Configuration Loading Priority

Configuration values are loaded in the following priority order (highest first):

1. **Environment Variables** (`FABRICATIO_*`)
2. **Local TOML File** (`fabricatio.toml`)
3. **pyproject.toml** (`[tool.fabricatio]`)
4. **Global TOML File** (platform-specific config directory)
5. **Default Values** (built-in defaults)

## Validation Rules

The configuration system enforces various validation rules:

- **URLs**: Must be valid HTTP/HTTPS URLs
- **Timeouts**: Minimum value of 1 second
- **Retry Counts**: Minimum value of 1
- **Temperature**: Range 0.0 to 2.0
- **Top-p**: Range 0.0 to 1.0
- **Penalties**: Range -2.0 to 2.0

## Secure Data Handling

The `SecretStr` type provides secure handling of sensitive information:

```rust
use fabricatio_config::SecretStr;

let api_key = SecretStr::new("sensitive-api-key");

// Safe for logging/debugging (shows "REDACTED")
println!("API Key: {}", api_key);

// Access the actual value when needed
let actual_key = api_key.get_secret_value();
```

## Dependencies

- `serde` & `serde_json`: Serialization and deserialization
- `figment`: Configuration management with multiple providers
- `validator`: Configuration validation
- `dotenvy`: Environment variable loading
- `pyo3` & `pyo3-stub-gen`: Python bindings and stub generation
- `pythonize`: Python object conversion
- `fabricatio-constants`: Application constants
- `macro-utils`: Template utilities

## Examples

See the `examples` directory for complete usage examples demonstrating configuration loading from various sources and Python integration.

## License

This crate is part of the Fabricatio project and follows the same licensing terms.