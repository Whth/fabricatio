//! Concrete model implementations for LLM providers.
//!
//! This module re-exports the available model types:
//! - [`crate::models::openai::OpenaiModel`] - OpenAI API compatible models
//! - [`crate::models::responses::OpenaiResponsesModel`] - OpenAI Responses API models
//! - `JevModel` - TypeSafe's Jev, over the System One evaluation API (with the `jev` feature on)
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
#[cfg(feature = "jev")]
pub mod jev;
pub mod openai;
pub mod responses;

pub use dummy::*;
#[cfg(feature = "jev")]
pub use jev::*;
pub use openai::*;
pub use responses::*;
