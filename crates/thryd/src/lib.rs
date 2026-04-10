//! Thryd - A lightweight, embedded LLM request router with caching.
//!
//! This library provides:
//! - Multi-provider LLM request routing
//! - Token usage tracking and rate limiting
//! - Persistent request caching
//! - Multiple routing strategies (round-robin, least-loaded, first-available)

pub mod cache;
pub mod connections;
pub mod constants;
mod deployment;
pub mod error;
mod model;
pub mod models;
pub mod provider;
pub mod route;
pub mod tracker;
pub(crate) mod utils;

pub use cache::*;
pub use constants::*;
pub use error::{Result, ThrydError};
pub use model::*;

pub use models::{dummy::*, openai::*};
pub use provider::{ProviderType, create_provider, dummy::*, openai::*};
pub use route::*;
pub use tracker::{UsageTracker, count_token, count_token_no_cache, count_token_prime_cache};
