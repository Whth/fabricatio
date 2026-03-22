use error_mapping::AsPyErr;
use once_cell::sync::Lazy;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use pyo3_stub_gen::derive::gen_stub_pyfunction;
use std::sync::Arc;
use thryd::tracker::Quota;
use thryd::{
    CompletionRequest, CompletionTag, EmbeddingRequest, EmbeddingTag, ProviderType, Router,
    create_provider,
};
use tokio::sync::RwLock;

pub static COMPLETION_MODEL_ROUTER: Lazy<Arc<RwLock<Router<CompletionTag>>>> =
    Lazy::new(|| Arc::new(RwLock::new(Router::default())));

pub static EMBEDDING_MODEL_ROUTER: Lazy<Arc<RwLock<Router<EmbeddingTag>>>> =
    Lazy::new(|| Arc::new(RwLock::new(Router::default())));

#[allow(clippy::too_many_arguments)]
#[gen_stub_pyfunction]
#[gen_stub(
    override_return_type(type_repr = "typing.Awaitable[str]",imports=("typing",))
)]
#[pyfunction]
#[pyo3(signature=(send_to, message, top_p,temperature,stream=false,max_completion_tokens=32_000,presence_penalty=0.,frequency_penalty=0.)
)]

/// Sends a completion request to the specified group and returns the full response.
///
/// Note: Although a 'stream' argument exists for protocol compatibility, this
/// implementation always aggregates the full response before returning.
/// It does not yield chunks asynchronously.
///
/// Args:
///     send_to (str): The router group name.
///     message (str): The user prompt content.
///     top_p (float): Nucleus sampling parameter. Defaults to 1.0.
///     temperature (float): Controls randomness. Defaults to 0.7.
///     stream (bool): Logical flag for compatibility. No performance difference. Defaults to False.
///     max_completion_tokens (int): Maximum tokens to generate. Defaults to 2048.
///     presence_penalty (float): Penalizes new tokens based on presence. Defaults to 0.0.
///     frequency_penalty (float): Penalizes new tokens based on frequency. Defaults to 0.0.
///
/// Returns:
///     str: The complete aggregated response content.
pub fn completion(
    python: Python,
    send_to: String,
    message: String,
    top_p: f32,
    temperature: f32,
    stream: bool,
    max_completion_tokens: u32,
    presence_penalty: f32,
    frequency_penalty: f32,
) -> PyResult<Bound<PyAny>> {
    let req = CompletionRequest {
        message,
        top_p,
        temperature,
        stream,
        max_completion_tokens,
        presence_penalty,
        frequency_penalty,
    };

    future_into_py(python, async move {
        COMPLETION_MODEL_ROUTER
            .read()
            .await
            .invoke(send_to, req)
            .await
            .into_pyresult()
    })
}

#[gen_stub_pyfunction]
#[gen_stub(
    override_return_type(type_repr = "typing.Awaitable[typing.List[typing.List[float]]]",imports=("typing",)
    )
)]
#[pyfunction]
/// Sends an embedding request to the specified group.
pub fn embedding(python: Python, send_to: String, texts: Vec<String>) -> PyResult<Bound<PyAny>> {
    let req = EmbeddingRequest { texts };

    future_into_py(python, async move {
        EMBEDDING_MODEL_ROUTER
            .read()
            .await
            .invoke(send_to, req)
            .await
            .into_pyresult()
    })
}

#[gen_stub_pyfunction()]
#[pyfunction]
#[gen_stub(
    override_return_type(type_repr = "typing.Awaitable[None]",imports=("typing",)
    )
)]
#[pyo3(signature=(provider_type,name=None,api_key=None,endpoint=None))]
/// Adds a provider to the router.
pub fn add_provider<'a>(
    python: Python<'a>,
    provider_type: ProviderType,
    name: Option<String>,
    api_key: Option<String>,
    endpoint: Option<String>,
) -> PyResult<Bound<'a, PyAny>> {
    let p = create_provider(provider_type, name, api_key, endpoint).into_pyresult()?;

    future_into_py(python, async move {
        COMPLETION_MODEL_ROUTER
            .write()
            .await
            .add_provider(p.clone())
            .into_pyresult()?;
        EMBEDDING_MODEL_ROUTER
            .write()
            .await
            .add_provider(p)
            .into_pyresult()?;
        Ok(())
    })
}
#[gen_stub_pyfunction]
#[pyfunction]
#[gen_stub(
    override_return_type(type_repr = "typing.Awaitable[None]",imports=("typing",)
    )
)]
#[pyo3(signature=(group,model_identifier,rpm=None,tpm=None))]
/// Adds a completion model to the specified group.
pub fn add_completion_model(
    python: Python,
    group: String,
    model_identifier: String,
    rpm: Option<Quota>,
    tpm: Option<Quota>,
) -> PyResult<Bound<PyAny>> {
    future_into_py(python, async move {
        COMPLETION_MODEL_ROUTER
            .write()
            .await
            .deploy(group, model_identifier, rpm, tpm)
            .into_pyresult()?;
        Ok(())
    })
}

#[gen_stub_pyfunction]
#[pyfunction]
#[gen_stub(
    override_return_type(type_repr = "typing.Awaitable[None]",imports=("typing",)
    )
)]
#[pyo3(signature=(group,model_identifier,rpm=None,tpm=None))]
/// Adds an embedding model to the specified group.
pub fn add_embedding_model(
    python: Python,
    group: String,
    model_identifier: String,
    rpm: Option<Quota>,
    tpm: Option<Quota>,
) -> PyResult<Bound<PyAny>> {
    future_into_py(python, async move {
        EMBEDDING_MODEL_ROUTER
            .write()
            .await
            .deploy(group, model_identifier, rpm, tpm)
            .into_pyresult()?;
        Ok(())
    })
}

#[gen_stub_pyfunction]
#[pyfunction]
/// Count tokens of a text
pub fn tokens_of(text: String) -> u64 {
    thryd::count_token(text)
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(completion, m)?)?;
    m.add_function(wrap_pyfunction!(embedding, m)?)?;
    m.add_function(wrap_pyfunction!(add_provider, m)?)?;
    m.add_function(wrap_pyfunction!(add_completion_model, m)?)?;
    m.add_function(wrap_pyfunction!(add_embedding_model, m)?)?;
    m.add_function(wrap_pyfunction!(tokens_of, m)?)?;
    m.add_class::<ProviderType>()?;
    Ok(())
}
