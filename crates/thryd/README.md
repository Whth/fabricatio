# Thryd

[![Crates.io](https://img.shields.io/crates/v/thryd.svg)](https://crates.io/crates/thryd)
[![Documentation](https://docs.rs/thryd/badge.svg)](https://docs.rs/thryd)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A lightweight, embedded LLM request router with intelligent caching, token usage tracking, and rate limiting.

## Overview

Thryd is a Rust library designed to manage and route requests to multiple LLM providers with built-in caching, quota management, and load balancing. It provides a unified interface for working with different LLM APIs while handling rate limits, token counting, and request optimization automatically.

### Key Features

- **Multi-provider routing**: Support for OpenAI-compatible APIs and custom providers
- **Intelligent caching**: Persistent request caching with automatic deduplication
- **Token tracking**: Accurate token counting using tiktoken
- **Rate limiting**: Configurable RPM (requests per minute) and TPM (tokens per minute) quotas
- **Load balancing**: Multiple routing strategies (round-robin, least-loaded, first-available)
- **Async-first**: Built on Tokio for high-performance concurrent requests
- **Extensible**: Easy to add new providers and model types

## Installation

Add Thryd to your `Cargo.toml`:

```toml
[dependencies]
thryd = "0.2"
```

Or with specific features:

```toml
[dependencies]
thryd = { version = "0.2", features = ["pyo3"] }
```

### Feature Flags

- `pyo3`: Enables Python bindings via PyO3
- `pystub`: Generates Python type stubs for better IDE support

## Quick Start

### Basic Usage

```rust
use thryd::*;
use secrecy::SecretString;
use std::sync::Arc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create an OpenAI provider
    let api_key = SecretString::from("your-api-key-here".to_string());
    let openai_provider = Arc::new(OpenaiCompatible::openai(api_key));
    
    // Create a router for completions
    let mut router = Router::<CompletionTag>::default();
    
    // Add the provider
    router.add_provider(openai_provider)?;
    
    // Deploy a model with rate limits
    router.deploy(
        "default".to_string(),
        "openai::gpt-4".to_string(),
        Some(60),  // 60 RPM
        Some(100_000),  // 100k TPM
    )?;
    
    // Make a completion request
    let request = CompletionRequest {
        message: "Hello, world!".to_string(),
        top_p: 0.9,
        temperature: 0.7,
        stream: false,
        max_completion_tokens: 100,
        presence_penalty: 0.0,
        frequency_penalty: 0.0,
    };
    
    let response = router.invoke("default".to_string(), request).await?;
    println!("Response: {}", response);
    
    Ok(())
}
```

### With Caching

```rust
use thryd::*;
use std::path::PathBuf;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut router = Router::<CompletionTag>::default();
    
    // Mount a persistent cache
    router.mount_cache(PathBuf::from("./llm-cache.db"))?;
    
    // Configure providers and deployments...
    
    // Subsequent identical requests will be served from cache
    let request = CompletionRequest {
        message: "What is the capital of France?".to_string(),
        // ... other parameters
    };
    
    // First call hits the API
    let response1 = router.invoke("default".to_string(), request.clone()).await?;
    
    // Second identical call returns cached result
    let response2 = router.invoke("default".to_string(), request).await?;
    
    assert_eq!(response1, response2);
    
    Ok(())
}
```

## Core Concepts

### Providers

Providers represent LLM API services. Thryd includes built-in support for:

- **OpenAICompatible**: Works with OpenAI API and compatible services (Azure OpenAI, LocalAI, etc.)
- **DummyProvider**: For testing and development

Implement the `Provider` trait to add custom providers.

### Models

Models represent specific LLM instances with their capabilities:

- **CompletionModel**: For text generation tasks
- **EmbeddingModel**: For text embedding tasks

### Deployments

Deployments wrap models with usage tracking and rate limiting:

```rust
// Create a deployment with rate limits
let deployment = Deployment::new(model)
    .with_usage_constrain(
        Some(60),   // 60 requests per minute
        Some(100_000), // 100,000 tokens per minute
    );
```

### Routers

Routers manage multiple deployments and route requests based on configured strategies:

- **CompletionTag**: For completion/chat requests
- **EmbeddingTag**: For embedding requests

## Advanced Usage

### Multiple Providers and Load Balancing

```rust
use thryd::*;

let mut router = Router::<CompletionTag>::default();

// Add multiple providers
router.add_provider(openai_provider)?;
router.add_provider(anthropic_provider)?; // Assuming custom provider

// Deploy models from different providers to the same group
router.deploy("chat".to_string(), "openai::gpt-4".to_string(), Some(30), Some(50_000))?;
router.deploy("chat".to_string(), "anthropic::claude-3".to_string(), Some(20), Some(40_000))?;

// Requests to "chat" group will be load-balanced between available deployments
```

### Token Usage Tracking

```rust
use thryd::tracker::*;

let mut tracker = UsageTracker::with_quota(
    Some(100_000),  // TPM quota
    Some(60),       // RPM quota
);

// Track a request
tracker.add_request_raw(
    "Hello, world!".to_string(),
    "Hi there!".to_string(),
);

// Check remaining quota
let remaining_tpm = tracker.remaining_tpm_quota();
let remaining_rpm = tracker.remaining_rpm_quota();

// Calculate wait time for a new request
let wait_time = tracker.need_wait_for_string("Another request".to_string());
```

### Custom Providers

```rust
use thryd::provider::Provider;
use async_trait::async_trait;
use http::HeaderMap;
use reqwest::Url;
use std::sync::Arc;

struct CustomProvider {
    endpoint: Url,
    api_key: String,
}

#[async_trait]
impl Provider for CustomProvider {
    fn provider_name(&self) -> &str {
        "custom"
    }
    
    fn endpoint(&self) -> Url {
        self.endpoint.clone()
    }
    
    fn headers(&self) -> Result<HeaderMap> {
        let mut headers = HeaderMap::new();
        headers.insert("Authorization", format!("Bearer {}", self.api_key).parse()?);
        Ok(headers)
    }
    
    // Implement create_completion_model and create_embedding_model...
}
```

## Configuration

### Environment Variables

- `OPENAI_API_KEY`: API key for OpenAI provider (used by `OpenaiCompatible::openai_from_env()`)

### Rate Limiting Configuration

Thryd uses a sliding window algorithm for rate limiting with configurable parameters:

- **BUCKET_COUNT**: Number of time buckets (default: 60)
- **BUCKETS_WINDOW_S**: Window size in seconds (default: 60)

These can be adjusted in `constants.rs` for fine-grained control.

## Performance

Thryd is designed for efficiency:

- **Zero-copy deserialization** where possible
- **Connection pooling** via reqwest
- **Lock-free** data structures for concurrent access
- **Async caching** with persistent storage

## Python Bindings

When built with the `pyo3` feature, Thryd provides Python bindings:

```python
import thryd

# Create a router
router = thryd.Router.completion()

# Add OpenAI provider
openai = thryd.OpenaiCompatible("your-api-key")
router.add_provider(openai)

# Make requests
response = router.invoke(
    "default",
    thryd.CompletionRequest(
        message="Hello, world!",
        temperature=0.7,
        max_tokens=100
    )
)
```

## Examples

### Embedding Generation

```rust
use thryd::*;
use secrecy::SecretString;
use std::sync::Arc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create an OpenAI provider
    let api_key = SecretString::from("your-api-key-here".to_string());
    let openai_provider = Arc::new(OpenaiCompatible::openai(api_key));
    
    // Create a router for embeddings
    let mut router = Router::<EmbeddingTag>::default();
    
    // Add the provider
    router.add_provider(openai_provider)?;
    
    // Deploy an embedding model
    router.deploy(
        "embeddings".to_string(),
        "openai::text-embedding-3-small".to_string(),
        Some(3000),  // 3000 RPM for embeddings
        Some(1_000_000),  // 1M TPM
    )?;
    
    // Make an embedding request
    let request = EmbeddingRequest {
        texts: vec![
            "The quick brown fox jumps over the lazy dog.".to_string(),
            "Artificial intelligence is transforming the world.".to_string(),
        ],
    };
    
    let embeddings = router.invoke("embeddings".to_string(), request).await?;
    println!("Generated {} embeddings", embeddings.len());
    
    Ok(())
}
```

### Error Handling

```rust
use thryd::*;
use thryd::error::ThrydError;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut router = Router::<CompletionTag>::default();
    
    // Try to invoke without any deployments
    let request = CompletionRequest {
        message: "Test".to_string(),
        top_p: 0.9,
        temperature: 0.7,
        stream: false,
        max_completion_tokens: 100,
        presence_penalty: 0.0,
        frequency_penalty: 0.0,
    };
    
    match router.invoke("nonexistent".to_string(), request).await {
        Ok(response) => println!("Got response: {}", response),
        Err(ThrydError::Router(msg)) => {
            println!("Router error: {}", msg);
            // Handle router errors (e.g., no deployments available)
        }
        Err(ThrydError::Provider(msg)) => {
            println!("Provider error: {}", msg);
            // Handle provider errors (e.g., API key invalid)
        }
        Err(ThrydError::Cache(msg)) => {
            println!("Cache error: {}", msg);
            // Handle cache errors
        }
        Err(e) => {
            println!("Other error: {}", e);
            // Handle other errors
        }
    }
    
    Ok(())
}
```

### Concurrent Requests

```rust
use thryd::*;
use secrecy::SecretString;
use std::sync::Arc;
use futures::future::join_all;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let api_key = SecretString::from("your-api-key-here".to_string());
    let openai_provider = Arc::new(OpenaiCompatible::openai(api_key));
    
    let mut router = Router::<CompletionTag>::default();
    router.add_provider(openai_provider)?;
    
    // Deploy multiple models for load balancing
    router.deploy("chat".to_string(), "openai::gpt-3.5-turbo".to_string(), Some(60), Some(100_000))?;
    router.deploy("chat".to_string(), "openai::gpt-4".to_string(), Some(20), Some(50_000))?;
    
    // Create multiple requests
    let requests = vec![
        CompletionRequest {
            message: "What is Rust?".to_string(),
            top_p: 0.9,
            temperature: 0.7,
            stream: false,
            max_completion_tokens: 100,
            presence_penalty: 0.0,
            frequency_penalty: 0.0,
        },
        CompletionRequest {
            message: "Explain async programming".to_string(),
            top_p: 0.9,
            temperature: 0.7,
            stream: false,
            max_completion_tokens: 150,
            presence_penalty: 0.0,
            frequency_penalty: 0.0,
        },
        CompletionRequest {
            message: "What are LLMs?".to_string(),
            top_p: 0.9,
            temperature: 0.7,
            stream: false,
            max_completion_tokens: 120,
            presence_penalty: 0.0,
            frequency_penalty: 0.0,
        },
    ];
    
    // Execute requests concurrently
    let futures = requests.into_iter().map(|req| {
        router.invoke("chat".to_string(), req)
    });
    
    let results = join_all(futures).await;
    
    for (i, result) in results.iter().enumerate() {
        match result {
            Ok(response) => println!("Request {}: {}", i + 1, response),
            Err(e) => println!("Request {} failed: {}", i + 1, e),
        }
    }
    
    Ok(())
}
```

### Monitoring and Metrics

```rust
use thryd::*;
use secrecy::SecretString;
use std::sync::Arc;
use std::time::Duration;
use tokio::time::sleep;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let api_key = SecretString::from("your-api-key-here".to_string());
    let openai_provider = Arc::new(OpenaiCompatible::openai(api_key));
    
    let mut router = Router::<CompletionTag>::default();
    router.add_provider(openai_provider)?;
    
    // Create a deployment with tracking
    let deployment = Deployment::new(
        OpenaiModel::new("gpt-3.5-turbo".to_string(), openai_provider.clone())
    ).with_usage_constrain(Some(10), Some(5_000));  // 10 RPM, 5k TPM
    
    // Simulate usage
    for i in 0..15 {
        let request = CompletionRequest {
            message: format!("Request number {}", i),
            top_p: 0.9,
            temperature: 0.7,
            stream: false,
            max_completion_tokens: 50,
            presence_penalty: 0.0,
            frequency_penalty: 0.0,
        };
        
        // Check if we need to wait due to rate limits
        let wait_time = deployment.min_cooldown_time(request.message.clone()).await;
        if wait_time > 0 {
            println!("Waiting {}ms due to rate limits...", wait_time);
            sleep(Duration::from_millis(wait_time)).await;
        }
        
        match deployment.completion(request).await {
            Ok(response) => println!("Response {}: {}", i, response),
            Err(e) => println!("Error on request {}: {}", i, e),
        }
        
        // Small delay between requests
        sleep(Duration::from_millis(100)).await;
    }
    
    Ok(())
}
```

Check the `examples/` directory in the repository for more comprehensive examples:

1. **Basic chat completion**
2. **Embedding generation**
3. **Multi-provider routing**
4. **Caching strategies**
5. **Rate limit simulation**
6. **Error handling patterns**
7. **Concurrent request management**

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](../../CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/your-org/fabricatio
cd fabricatio

# Build the crate
cargo build --package thryd

# Run tests
cargo test --package thryd

# Run benchmarks
cargo bench --package thryd
```

### Testing

```bash
# Run all tests
cargo test

# Run tests with specific features
cargo test --features pyo3

# Run documentation tests
cargo test --doc
```

## License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.

## Acknowledgments

- [tiktoken-rs](https://github.com/openai/tiktoken-rs) for token counting
- [async-openai](https://github.com/64bit/async-openai) for OpenAI API client inspiration
- [redb](https://github.com/cberner/redb) for embedded database storage

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and changes.

---

**Thryd**: From Old Norse "þrýðr" meaning "strength, force" - giving your LLM applications the power to scale.