use error_mapping::AsPyErr;
use fabricatio_config::SecretStr;
use fabricatio_constants::ROUTER_VARNAME;
use once_cell::sync::Lazy;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pyfunction, gen_stub_pymethods};
use std::path::PathBuf;
use std::sync::Arc;
use thryd::tracker::Quota;
use thryd::{
    CompletionRequest, CompletionTag, EmbeddingRequest, EmbeddingTag, ProviderType,
    Router as ThrydRouter, create_provider,
};
use tokio::sync::RwLock;

#[gen_stub_pyclass]
#[pyclass]
#[derive(Default)]
struct Router {
    embedding_router: Arc<RwLock<ThrydRouter<EmbeddingTag>>>,
    completion_router: Arc<RwLock<ThrydRouter<CompletionTag>>>,
}

#[gen_stub_pymethods]
#[pymethods]
impl Router {
    #[allow(clippy::too_many_arguments)]
    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[str]", imports = ("typing",))
    )]
    #[pyo3(signature = (send_to, message, top_p, temperature, stream = false, max_completion_tokens = 32_000, presence_penalty = 0., frequency_penalty = 0.)
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
    pub fn completion<'a>(
        &self,
        python: Python<'a>,
        send_to: String,
        message: String,
        top_p: f32,
        temperature: f32,
        stream: bool,
        max_completion_tokens: u32,
        presence_penalty: f32,
        frequency_penalty: f32,
    ) -> PyResult<Bound<'a, PyAny>> {
        let req = CompletionRequest {
            message,
            top_p,
            temperature,
            stream,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
        };

        let r = self.completion_router.clone();

        future_into_py(python, async move {
            r.read().await.invoke(send_to, req).await.into_pyresult()
        })
    }

    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[typing.List[typing.List[float]]]", imports = ("typing",)
        )
    )]
    /// Sends an embedding request to the specified group.
    pub fn embedding<'a>(
        &self,
        python: Python<'a>,
        send_to: String,
        texts: Vec<String>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let req = EmbeddingRequest { texts };

        let r = self.embedding_router.clone();

        future_into_py(python, async move {
            r.read().await.invoke(send_to, req).await.into_pyresult()
        })
    }

    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[None]", imports = ("typing",))
    )]
    #[pyo3(signature = (provider_type, name = None, api_key = None, endpoint = None))]
    /// Adds a provider to the router.
    pub fn add_provider<'a>(
        &self,
        python: Python<'a>,
        provider_type: ProviderType,
        name: Option<String>,
        api_key: Option<SecretStr>,
        endpoint: Option<String>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let p = create_provider(
            provider_type,
            name,
            api_key.map(|k| k.get_secret_value().to_string()),
            endpoint,
        )
        .into_pyresult()?;

        let er = self.embedding_router.clone();
        let cr = self.completion_router.clone();

        future_into_py(python, async move {
            cr.write().await.add_provider(p.clone()).into_pyresult()?;
            er.write().await.add_provider(p).into_pyresult()?;
            Ok(())
        })
    }

    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[None]", imports = ("typing",))
    )]
    #[pyo3(signature = (group, model_identifier, rpm = None, tpm = None))]
    /// Adds a completion model to the specified group.
    pub fn add_completion_model<'a>(
        &self,

        python: Python<'a>,
        group: String,
        model_identifier: String,
        rpm: Option<Quota>,
        tpm: Option<Quota>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let cr = self.completion_router.clone();
        future_into_py(python, async move {
            cr.write()
                .await
                .deploy(group, model_identifier, rpm, tpm)
                .into_pyresult()?;
            Ok(())
        })
    }

    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[None]", imports = ("typing",))
    )]
    #[pyo3(signature = (group, model_identifier, rpm = None, tpm = None))]
    /// Adds an embedding model to the specified group.
    pub fn add_embedding_model<'a>(
        &self,
        python: Python<'a>,
        group: String,
        model_identifier: String,
        rpm: Option<Quota>,
        tpm: Option<Quota>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let er = self.embedding_router.clone();

        future_into_py(python, async move {
            er.write()
                .await
                .deploy(group, model_identifier, rpm, tpm)
                .into_pyresult()?;
            Ok(())
        })
    }

    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[None]", imports = ("typing",))
    )]
    /// Mount cache database to all routers, create if not exists
    pub fn mount_cache<'a>(
        &self,
        python: Python<'a>,
        file_path: PathBuf,
    ) -> PyResult<Bound<'a, PyAny>> {
        let er = self.embedding_router.clone();
        let cr = self.completion_router.clone();

        future_into_py(python, async move {
            er.write()
                .await
                .mount_cache(file_path.clone())
                .into_pyresult()?;
            cr.write().await.mount_cache(file_path).into_pyresult()?;
            Ok(())
        })
    }
}

#[gen_stub_pyfunction]
#[pyfunction]
/// Count tokens of a text
pub fn tokens_of(text: String) -> u64 {
    thryd::count_token(text)
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(tokens_of, m)?)?;
    m.add_class::<ProviderType>()?;
    m.add_class::<Router>()?;
    m.add(ROUTER_VARNAME, Router::default())?;
    Ok(())
}
