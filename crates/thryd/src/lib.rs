#![feature(associated_type_defaults)]
#![feature(map_try_insert)]
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
pub mod error;
pub mod provider;
pub mod route;
pub mod tracker;
mod deployment;
mod message;
mod model;
pub mod models;
pub(crate) mod utils;


pub use cache::*;
pub use constants::*;
pub use error::{Result, ThrydError};
pub use model::*;

pub use models::{
    dummy::*, openai::*,
};
pub use provider::{
    dummy::*, openai::*,
};
pub use route::*;
pub use tracker::UsageTracker;
