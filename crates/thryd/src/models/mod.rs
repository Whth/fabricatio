//! Concrete model implementations for LLM providers.
//!
//! This module re-exports the available model types:
//! - [`crate::models::openai::OpenaiModel`] - OpenAI API compatible models
//! - [`crate::models::dummy::DummyModel`] - Mock models for testing
//!
//! # Creating Models
//!
//! Models are typically created through a [`Provider`](crate::provider::Provider):
//!
//! ```rust,ignore
//! use thryd::OpenaiCompatible;
//! use std::sync::Arc;
//!
//! let provider = Arc::new(OpenaiCompatible::openai(api_key));
//! let model = provider.create_completion_model("gpt-4".to_string())?;
//! ```
//!
//! See individual model modules for details.

pub mod dummy;
pub mod openai;

pub use dummy::*;
pub use openai::*;
