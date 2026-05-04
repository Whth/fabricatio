//! Thryd - A lightweight, embedded LLM request router with caching.
//!
//! Thryd is a Rust library for routing requests to multiple LLM providers with built-in
//! caching, token usage tracking, rate limiting, and load balancing. It provides a unified
//! interface for working with different LLM APIs while handling rate limits, token counting,
//! and request optimization automatically.
//!
//! # Key Features
//!
//! - **Multi-provider routing**: Support for OpenAI-compatible APIs and custom providers
//! - **Intelligent caching**: Persistent request caching with automatic deduplication
//! - **Token tracking**: Accurate token counting using tiktoken
//! - **Rate limiting**: Configurable RPM (requests per minute) and TPM (tokens per minute) quotas
//! - **Load balancing**: Multiple routing strategies (round-robin, least-loaded, first-available)
//! - **Async-first**: Built on Tokio for high-performance concurrent requests
//! - **Extensible**: Easy to add new providers and model types
//!
//! # Crate Organization
//!
//! The crate is organized into the following public modules:
//!
//! | Module | Description |
//! |--------|-------------|
//! | `cache` | Persistent request caching backed by redb |
//! | `connections` | HTTP client connection management and pooling |
//! | `constants` | Rate limiting and configuration constants |
//! | `error` | Error types and result handling |
//! | `models` | LLM model definitions and implementations |
//! | `provider` | Provider implementations and factory functions |
//! | `route` | Request routing and load balancing logic |
//! | `tracker` | Token usage tracking and rate limiting |
//!
//! # Usage Example
//!
//! Here's a comprehensive example demonstrating how to use thryd:
//!
//! ```ignore
//! use thryd::*;
//! use secrecy::SecretString;
//! use std::sync::Arc;
//! use std::path::PathBuf;
//!
//! #[tokio::main]
//! async fn main() -> Result<(), Box<dyn std::error::Error>> {
//!     // 1. Create a provider
//!     let api_key = SecretString::from("your-api-key-here".to_string());
//!     let openai_provider = Arc::new(OpenaiCompatible::openai(api_key));
//!
//!     // 2. Create a router for completions
//!     let mut router = Router::<CompletionTag>::default();
//!
//!     // 3. Mount persistent cache (optional but recommended)
//!     router.mount_cache(PathBuf::from("./llm-cache.db"))?;
//!
//!     // 4. Add the provider to the router
//!     router.add_provider(openai_provider)?;
//!
//!     // 5. Deploy a model with rate limits
//!     router.deploy(
//!         "default".to_string(),
//!         "openai::gpt-4".to_string(),
//!         Some(60),          // 60 requests per minute
//!         Some(100_000),     // 100,000 tokens per minute
//!     )?;
//!
//!     // 6. Create and make a request
//!     let request = CompletionRequest {
//!         message: "Explain the difference between async and sync programming.".to_string(),
//!         top_p: 0.9,
//!         temperature: 0.7,
//!         stream: false,
//!         max_completion_tokens: 200,
//!         presence_penalty: 0.0,
//!         frequency_penalty: 0.0,
//!     };
//!
//!     // First request hits the API
//!     let response = router.invoke("default".to_string(), request).await?;
//!     println!("Response: {}", response);
//!
//!     // Subsequent identical requests are served from cache
//!
//!     Ok(())
//! }
//! ```
//!
//! # Architecture Overview
//!
//! ## Providers
//!
//! Providers represent LLM API endpoints. The main provider types are:
//!
//! - [`OpenaiCompatible`] - Works with OpenAI API and compatible services
//! - [`DummyProvider`] - For testing without API calls
//!
//! ## Models
//!
//! Models represent specific LLM instances. The traits are:
//!
//! - `CompletionModel` trait - For text generation tasks
//! - `EmbeddingModel` trait - For text embedding tasks
//!
//! ## Deployments
//!
//! Deployments wrap models with usage tracking and rate limiting. Created via [`Router::deploy`].
//!
//! ## Routers
//!
//! Routers manage multiple deployments and route requests based on configured strategies:
//!
//! - [`Router<CompletionTag>`] - For completion/chat requests
//! - [`Router<EmbeddingTag>`] - For embedding requests
//!
//! # Feature Flags
//!
//! - `pyo3`: Enables Python bindings via PyO3
//! - `stubgen`: Generates Python type stubs for better IDE support
//!
//! # Rate Limiting
//!
//! Thryd uses a sliding window algorithm for rate limiting. The constants `BUCKET_COUNT`
//! and `BUCKETS_WINDOW_S` in the [`constants`] module control the granularity of rate limit
//! tracking.

// Public modules
pub mod cache;
pub mod connections;
pub mod constants;
pub mod deployment;
pub mod error;
mod model;
pub mod models;
pub mod provider;
pub mod route;
pub mod tracker;
pub mod utils;

// Re-exports from submodules for ergonomic API access

/// Cache-related types for persistent request caching.
///
/// The main type is [`PersistentCache`] which provides a thread-safe,
/// persistent key-value cache backed by redb.
pub use cache::*;

/// Rate limiting and configuration constants.
///
/// Re-exports:
/// - `BUCKET_COUNT` - Number of time buckets for rate limiting
/// - `BUCKETS_WINDOW_S` - Window size in seconds for rate limiting
pub use constants::*;

/// Error types and result handling.
pub use error::{Result, ThrydError};

/// Model-related re-exports.
///
/// Re-exports from submodules:
/// - From `models`: `CompletionModel`, `EmbeddingModel`, `RerankerModel` traits
/// - From `models::dummy`: `DummyModel`
/// - From `models::openai`: `OpenaiModel`
pub use model::{CompletionRequestMessage, *};

/// Model definitions for different LLM providers.
///
/// Re-exports:
/// - `dummy` submodule with `DummyModel`
/// - `openai` submodule with `OpenaiModel`
pub use models::{dummy::*, openai::*};

/// Provider implementations and factory functions.
///
/// Re-exports:
/// - [`ProviderType`] - Enum of supported provider types
/// - [`create_provider`] - Factory function for creating providers
/// - `OpenaiCompatible` - OpenAI-compatible provider
/// - `DummyProvider` - Dummy provider for testing
pub use provider::{ProviderType, create_provider, dummy::*, openai::*};

/// Request routing, load balancing, and router implementation.
///
/// Re-exports:
/// - [`Router`] - Main router for managing deployments and routing requests
/// - [`CompletionTag`] - Tag type for completion requests
/// - [`EmbeddingTag`] - Tag type for embedding requests
pub use route::*;

/// Token usage tracking and rate limiting utilities.
///
/// Re-exports:
/// - [`UsageTracker`] - Token usage and quota tracker
/// - [`count_token`] - Count tokens with cache lookup
pub use tracker::{UsageTracker, count_token};
