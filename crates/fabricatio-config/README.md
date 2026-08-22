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
    // Completion request defaults
    llm: LLMConfig,

    // Named model tiers resolved via resolve_llm_variant()
    agent: Agent,

    // Embedding request defaults
    embedding: EmbeddingConfig,

    // Reranker request defaults
    reranker: RerankerConfig,

    // Logging settings
    debug: DebugConfig,

    // Core template names (default to built-in/<name>)
    templates: TemplateConfig,

    // Template discovery/loading
    template_manager: TemplateManagerConfig,

    // Providers, deployments, cache, retries
    routing: RoutingConfig,

    // Global behavior flags
    general: GeneralConfig,

    // Event emitter settings
    emitter: EmitterConfig,

    // Per-subpackage extension store (populated from [ext.<key>] tables)
    ext: HashMap<String, Value>,
}
```

### LLM Configuration (LLMConfig)

```rust
LLMConfig {
    send_to: Option<String>,               // Default routing group or agent variant
    no_cache: Option<bool>,                // Bypass the response cache
    temperature: Option<f32>,              // Range 0.0-2.0
    top_p: Option<f32>,                    // Range 0.0-1.0
    stream: bool,                          // Streaming responses (default false)
    max_completion_tokens: Option<u32>,    // Must be >= 1 if set
    presence_penalty: Option<f32>,         // Range -2.0-2.0
    frequency_penalty: Option<f32>,        // Range -2.0-2.0
    effort: Option<String>,                // Reasoning effort for models that support it
}
```

### Agent Configuration (Agent)

Maps model variant slots to routing groups; `resolve_llm_variant()` looks a
variant name up here and passes any non-variant string through unchanged.

```rust
Agent {
    tiny: Option<String>,   // Trivial jobs: classification, checks, short rewrites
    smol: Option<String>,   // Lightweight, low-context work
    task: Option<String>,   // Routine workhorse: drafting, extraction
    slow: Option<String>,   // Heavy reasoning, long context
    plan: Option<String>,   // Planning, quality-critical synthesis
}
```

### Embedding Configuration (EmbeddingConfig)

```rust
EmbeddingConfig {
    send_to: Option<String>,           // Default routing group for embedding requests
    no_cache: Option<bool>,            // Disable response caching for embeddings
    ndim: Option<u32>,                 // Dimensionality of output embedding vectors
    max_batch_emb_size: Option<usize>, // Split larger batches into parallel API calls
}
```

### Reranker Configuration (RerankerConfig)

```rust
RerankerConfig {
    send_to: Option<String>,          // Default routing group for reranker requests
    no_cache: Option<bool>,           // Disable response caching for reranker
}
```

The remaining sections (`debug`, `templates`, `template_manager`, `routing`,
`general`, `emitter`) are documented in the project's configuration guide at
`docs/source/configuration.rst`.

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
print(f"LLM Model: {config.llm.send_to}")
print(f"Log Level: {config.debug.log_level}")

# Use the load method for dynamic configuration
dynamic_config = config.load("my_section", MyPythonClass)
```

### Environment Variable Configuration

```bash
# Set configuration via environment variables
export FABRICATIO_LLM__SEND_TO="base"
export FABRICATIO_LLM__TEMPERATURE="0.7"
export FABRICATIO_LLM__MAX_COMPLETION_TOKENS="16000"
export FABRICATIO_DEBUG__LOG_LEVEL="DEBUG"

# Extension packages are configured under EXT__<KEY>__<FIELD>
export FABRICATIO_EXT__COMFYUI__BASE_URL="http://127.0.0.1:8188"
```

### TOML Configuration File

```toml
# fabricatio.toml
[debug]
log_level = "INFO"

[llm]
send_to = "base"
temperature = 0.7
max_completion_tokens = 16000
stream = false

[routing]
providers = [
    { ptype = "OpenAICompatible", key = "sk-...", name = "mm", base_url = "https://api.example.com/v1/" }
]
completion_deployments = [
    { id = "mm/gpt-4o-mini", group = 'base', tpm = 100_000, rpm = 1000 }
]
cache_database_path = ".cache.db"

[templates]
task_briefing_template = "built-in/task_briefing"
dependencies_template = "built-in/dependencies"

[ext.comfyui]          # extension package configuration
base_url = "http://127.0.0.1:8188"
timeout = 300.0
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