use error_mapping::AsPyErr;
use fabricatio_config::{Config, DeploymentConfig, ProviderConfig, SecretStr};
use fabricatio_logger::trace;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pyfunction, gen_stub_pymethods};
use std::path::PathBuf;
use std::sync::Arc;
use thryd::tracker::Quota;
use thryd::{
    CompletionRequest, CompletionTag, EmbeddingRequest, EmbeddingTag, ModelTypeTag,
    PersistentCache, ProviderType, Router as ThrydRouter, create_provider,
};
use tokio::sync::RwLock;

#[gen_stub_pyclass]
#[pyclass]
#[derive(Default)]
pub struct Router {
    embedding_router: Arc<RwLock<ThrydRouter<EmbeddingTag>>>,
    completion_router: Arc<RwLock<ThrydRouter<CompletionTag>>>,
}

impl Router {
    pub fn new(
        embedding_router: ThrydRouter<EmbeddingTag>,
        completion_router: ThrydRouter<CompletionTag>,
    ) -> Self {
        Self {
            embedding_router: Arc::new(RwLock::new(embedding_router)),
            completion_router: Arc::new(RwLock::new(completion_router)),
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl Router {
    #[allow(clippy::too_many_arguments)]
    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[str]", imports = ("typing",))
    )]
    #[pyo3(signature = (send_to, message,stream = false, top_p=None, temperature=None, max_completion_tokens = None, presence_penalty = None, frequency_penalty = None)
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
    ///     stream (bool): Logical flag for compatibility. No performance difference. Defaults to False.
    ///     top_p (Optional[float]): Nucleus sampling parameter. Defaults to 1.0 if None.
    ///     temperature (Optional[float]): Controls randomness. Defaults to 0.7 if None.
    ///     max_completion_tokens (Optional[int]): Maximum tokens to generate. Defaults to 2048 if None.
    ///     presence_penalty (Optional[float]): Penalizes new tokens based on presence. Defaults to 0.0 if None.
    ///     frequency_penalty (Optional[float]): Penalizes new tokens based on frequency. Defaults to 0.0 if None.
    ///
    /// Returns:
    ///     str: The complete aggregated response content.
    pub fn completion<'a>(
        &self,
        python: Python<'a>,
        send_to: String,
        message: String,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
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
    ///
    /// Args:
    ///     send_to (str): The router group name to route the embedding request.
    ///     texts (List[str]): A list of text strings to generate embeddings for.
    ///
    /// Returns:
    ///     List[List[float]]: A list of embedding vectors corresponding to the input texts.
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
    ///
    /// This method registers a new provider with both the completion and embedding routers.
    ///
    /// Args:
    ///     provider_type (ProviderType): The type of the provider (e.g., OpenAI, Anthropic).
    ///     name (Optional[str]): Optional custom name for the provider.
    ///     api_key (Optional[SecretStr]): Optional API key for authentication.
    ///     endpoint (Optional[str]): Optional custom API endpoint URL.
    ///
    /// Returns:
    ///     None: This is an asynchronous operation that modifies the router state.
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
            api_key.map(|k| k.get_secret_value().into()),
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
    ///
    /// Registers a new model identifier within a specific routing group for completion tasks.
    ///
    /// Args:
    ///     group (str): The target router group name.
    ///     model_identifier (str): The unique identifier of the model to be added.
    ///     rpm (Optional[int]): Optional requests per minute limit.
    ///     tpm (Optional[int]): Optional tokens per minute limit.
    ///
    /// Returns:
    ///     None: This is an asynchronous operation that modifies the router state.
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
    ///
    /// Registers a new model identifier within a specific routing group for embedding tasks.
    ///
    /// Args:
    ///     group (str): The target router group name.
    ///     model_identifier (str): The unique identifier of the model to be added.
    ///     rpm (Optional[Quota]): Optional requests per minute limit.
    ///     tpm (Optional[Quota]): Optional tokens per minute limit.
    ///
    /// Returns:
    ///     None: This is an asynchronous operation that modifies the router state.
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
    /// Mount cache database to all routers, create if not exists.
    ///
    /// Initializes and mounts a shared cache database file for both completion and embedding routers.
    /// If the database does not exist, it will be created automatically.
    ///
    /// Args:
    ///     file_path (PathBuf): The absolute or relative path to the cache database file.
    ///
    /// Returns:
    ///     None: This is an asynchronous operation that modifies the router state.
    pub fn mount_cache<'a>(
        &self,
        python: Python<'a>,
        file_path: PathBuf,
    ) -> PyResult<Bound<'a, PyAny>> {
        let er = self.embedding_router.clone();
        let cr = self.completion_router.clone();

        future_into_py(python, async move {
            let cache = PersistentCache::create_or_open(file_path).into_pyresult()?;

            er.write().await.mount_cache(cache.clone());
            cr.write().await.mount_cache(cache);
            Ok(())
        })
    }
}

pub fn add_providers_from_configs<T: ModelTypeTag>(
    mut router: ThrydRouter<T>,
    configs: Vec<ProviderConfig>,
) -> PyResult<ThrydRouter<T>> {
    for config in configs {
        let p = create_provider(
            config.ptype,
            config.name,
            config.key.map(|k| k.get_secret_value().into()),
            config.base_url,
        )
        .into_pyresult()?;

        router.add_provider(p).into_pyresult()?;
    }

    Ok(router)
}

pub fn add_models_from_configs<T: ModelTypeTag>(
    mut router: ThrydRouter<T>,
    configs: Vec<DeploymentConfig>,
) -> PyResult<ThrydRouter<T>> {
    for config in configs {
        router
            .deploy(config.group, config.id, config.rpm, config.tpm)
            .into_pyresult()?;
    }
    Ok(router)
}

pub fn init_router_from_config(config: &Config) -> PyResult<Router> {
    trace!("Initializing router from config");
    let cr = ThrydRouter::default();
    let cr = add_providers_from_configs(cr, config.routing.providers.clone())?;
    let mut cr = add_models_from_configs(cr, config.routing.completion_deployments.clone())?;

    let er = ThrydRouter::default();
    let er = add_providers_from_configs(er, config.routing.providers.clone())?;
    let mut er = add_models_from_configs(er, config.routing.embedding_deployments.clone())?;

    if let Some(p) = config.routing.cache_database_path.as_ref() {
        trace!("Mounting cache database at {}", p.display());
        let cache = PersistentCache::create_or_open(p).into_pyresult()?;
        cr.mount_cache(cache.clone());
        er.mount_cache(cache);
    }
    Ok(Router::new(er, cr))
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
    Ok(())
}
