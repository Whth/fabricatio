use error_mapping::AsPyErr;
use fabricatio_config::{DeploymentConfig, ProviderConfig, SecretStr};
use fabricatio_logger::{debug, error, trace};
use futures::FutureExt;
use futures::future::join_all;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use pyo3_stub_gen::derive::*;
use std::fs;
use std::sync::Arc;
use thryd::deployment::Deployment;
use thryd::tracker::Quota;
use thryd::utils::analyze_identifier;
use thryd::{
    Completion, CompletionModel, CompletionTag, DeploymentIdentifier, DummyModel,
    EmbeddingRequest, EmbeddingTag, Embeddings, ModelTypeTag, Ranking,
    RerankerRequest, RerankerTag, Router as ThrydRouter, create_provider,
};

pub use thryd::{CompletionRequest, ProviderType, RouteGroupName};

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(from_py_object)]
#[derive(Default, Clone)]
pub struct Router {
    pub embedding_router: Arc<ThrydRouter<EmbeddingTag>>,
    pub completion_router: Arc<ThrydRouter<CompletionTag>>,
    pub reranker_router: Arc<ThrydRouter<RerankerTag>>,
}

impl Router {
    pub fn new(
        embedding_router: ThrydRouter<EmbeddingTag>,
        completion_router: ThrydRouter<CompletionTag>,
        reranker_router: ThrydRouter<RerankerTag>,
    ) -> Self {
        Self {
            embedding_router: Arc::new(embedding_router),
            completion_router: Arc::new(completion_router),
            reranker_router: Arc::new(reranker_router),
        }
    }

    pub async fn embedding_rs(
        self,
        send_to: RouteGroupName,
        req: EmbeddingRequest,
        no_cache: bool,
    ) -> PyResult<Embeddings> {
        Self::embedding_inner(send_to, req, self.embedding_router.clone(), no_cache).await
    }

    pub async fn embedding_inner(
        send_to: RouteGroupName,
        req: EmbeddingRequest,
        r: Arc<ThrydRouter<EmbeddingTag>>,
        no_cache: bool,
    ) -> PyResult<Embeddings> {
        r.invoke(send_to.clone(), req, no_cache)
            .await
            .into_pyresult()
    }

    pub async fn rerank_inner(
        send_to: RouteGroupName,
        req: RerankerRequest,
        r: Arc<ThrydRouter<RerankerTag>>,
        no_cache: bool,
    ) -> PyResult<Ranking> {
        r.invoke(send_to.clone(), req, no_cache)
            .await
            .into_pyresult()
    }

    pub async fn completion_batch_rs(
        &self,
        send_to: RouteGroupName,
        reqs: Vec<CompletionRequest>,
        no_cache: bool,
    ) -> Vec<Option<Completion>> {
        Self::completion_batch_inner(send_to, reqs, self.completion_router.clone(), no_cache).await
    }

    pub async fn completion_batch_inner(
        send_to: RouteGroupName,
        reqs: Vec<CompletionRequest>,
        r: Arc<ThrydRouter<CompletionTag>>,
        no_cache: bool,
    ) -> Vec<Option<Completion>> {
        join_all(
            reqs.into_iter()
                .map(|req| r.invoke(send_to.clone(), req, no_cache)),
        )
        .map(|results| {
            results
                .into_iter()
                .map(|res| {
                    if res.is_ok() {
                        res.ok()
                    } else {
                        error!("Error in completion batch: {:?}", res);
                        None
                    }
                })
                .collect::<Vec<Option<Completion>>>()
        })
        .await
    }

    pub async fn completion_rs(
        self,
        send_to: RouteGroupName,
        req: CompletionRequest,
    ) -> PyResult<Completion> {
        Self::completion_inner(send_to, req, self.completion_router.clone(), false).await
    }
    pub async fn completion_inner(
        send_to: RouteGroupName,
        req: CompletionRequest,
        r: Arc<ThrydRouter<CompletionTag>>,
        no_cache: bool,
    ) -> PyResult<Completion> {
        r.invoke(send_to, req, no_cache).await.into_pyresult()
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[pymethods]
impl Router {
    #[allow(clippy::too_many_arguments)]
    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[str]", imports = ("typing",))
    )]
    #[pyo3(signature = (send_to, message,stream = false, top_p=None, temperature=None, max_completion_tokens = None, presence_penalty = None, frequency_penalty = None, no_cache = false)
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
    ///     no_cache (bool): Whether to bypass the cache for this request. Defaults to False.
    ///
    /// Returns:
    ///     str: The complete aggregated response content.
    pub fn completion<'a>(
        &self,
        python: Python<'a>,
        send_to: RouteGroupName,
        message: String,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
        no_cache: bool,
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
            Self::completion_inner(send_to, req, r, no_cache).await
        })
    }

    #[allow(clippy::too_many_arguments)]
    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[typing.List[str|None]]", imports = ("typing",)
        )
    )]
    #[pyo3(signature = (send_to, messages,stream = false, top_p=None, temperature=None, max_completion_tokens = None, presence_penalty = None, frequency_penalty = None, no_cache = false)
    )]
    /// Sends a batch of completion requests to the specified group and returns all responses.
    ///
    /// Note:
    ///     Although a 'stream' argument exists for protocol compatibility, this
    ///     implementation always aggregates the full response before returning.
    ///     It does not yield chunks asynchronously.
    ///
    /// Args:
    ///     send_to (RouteGroupName): The router group name to route the completion requests.
    ///     messages (List[str]): A list of user prompt contents.
    ///     stream (bool): Logical flag for compatibility. No performance difference. Defaults to False.
    ///     top_p (Optional[float]): Nucleus sampling parameter. Defaults to 1.0 if None.
    ///     temperature (Optional[float]): Controls randomness. Defaults to 0.7 if None.
    ///     max_completion_tokens (Optional[int]): Maximum tokens to generate. Defaults to 2048 if None.
    ///     presence_penalty (Optional[float]): Penalizes new tokens based on presence. Defaults to 0.0 if None.
    ///     frequency_penalty (Optional[float]): Penalizes new tokens based on frequency. Defaults to 0.0 if None.
    ///     no_cache (bool): Whether to bypass the cache for each request. Defaults to False.
    ///
    /// Returns:
    ///     List[str | None]: A list of complete aggregated response contents. Failed requests return None.
    pub fn completion_batch<'a>(
        &self,
        python: Python<'a>,
        send_to: RouteGroupName,
        messages: Vec<String>,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
        no_cache: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let reqs = messages
            .into_iter()
            .map(|message| CompletionRequest {
                message,
                top_p,
                temperature,
                stream,
                max_completion_tokens,
                presence_penalty,
                frequency_penalty,
            })
            .collect::<Vec<_>>();

        let r = self.completion_router.clone();

        future_into_py(python, async move {
            Ok(Self::completion_batch_inner(send_to, reqs, r, no_cache).await)
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
    ///     no_cache (bool): Whether to bypass the cache for this request. Defaults to False.
    ///
    /// Returns:
    ///     List[List[float]]: A list of embedding vectors corresponding to the input texts.
    #[pyo3(signature = (send_to, texts, no_cache = false))]
    pub fn embedding<'a>(
        &self,
        python: Python<'a>,
        send_to: RouteGroupName,
        texts: Vec<String>,
        no_cache: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let r = self.embedding_router.clone();

        future_into_py(python, async move {
            Self::embedding_inner(send_to, EmbeddingRequest { texts }, r, no_cache).await
        })
    }

    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[typing.List[typing.Tuple[int, float]]]", imports = ("typing",))
    )]
    /// Sends a reranking request to the specified group.
    ///
    /// Args:
    ///     send_to (str): The router group name to route the reranking request.
    ///     query (str): The query text to rank documents against.
    ///     documents (List[str]): A list of document texts to rerank.
    ///     no_cache (bool): Whether to bypass the cache for this request. Defaults to False.
    ///
    /// Returns:
    ///     List[Tuple[int, float]]: A list of (document_index, score) pairs sorted by relevance descending.
    #[pyo3(signature = (send_to, query, documents, no_cache = false))]
    pub fn rerank<'a>(
        &self,
        python: Python<'a>,
        send_to: RouteGroupName,
        query: String,
        documents: Vec<String>,
        no_cache: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let r = self.reranker_router.clone();
        let req = RerankerRequest { query, documents };
        future_into_py(python, async move {
            Self::rerank_inner(send_to, req, r, no_cache).await
        })
    }

    #[pyo3(signature = (provider_type, name = None, api_key = None, endpoint = None))]
    /// Adds a provider to the router.
    ///
    /// This method registers a new provider with the completion, embedding, and reranker routers.
    ///
    /// Args:
    ///     provider_type (ProviderType): The type of the provider (e.g., OpenAI, Anthropic).
    ///     name (Optional[str]): Optional custom name for the provider.
    ///     api_key (Optional[SecretStr]): Optional API key for authentication.
    ///     endpoint (Optional[str]): Optional custom API endpoint URL.
    ///
    /// Returns:
    ///     None: This is an asynchronous operation that modifies the router state.
    pub fn add_provider(
        &self,
        provider_type: ProviderType,
        name: Option<String>,
        api_key: Option<SecretStr>,
        endpoint: Option<String>,
    ) -> PyResult<()> {
        let p = create_provider(
            provider_type,
            name,
            api_key.map(|k| k.get_secret_value().into()),
            endpoint,
        )
        .into_pyresult()?;

        let er = self.embedding_router.clone();
        let cr = self.completion_router.clone();
        let rr = self.reranker_router.clone();

        cr.add_or_update_provider(p.clone());
        er.add_or_update_provider(p.clone());
        rr.add_or_update_provider(p);
        Ok(())
    }

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
    pub fn add_completion_model(
        &self,
        group: RouteGroupName,
        model_identifier: DeploymentIdentifier,
        rpm: Option<Quota>,
        tpm: Option<Quota>,
    ) -> PyResult<()> {
        let cr = self.completion_router.clone();
        cr.deploy(group, model_identifier, rpm, tpm)
            .into_pyresult()?;
        Ok(())
    }

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
    pub fn add_embedding_model(
        &self,
        group: RouteGroupName,
        model_identifier: DeploymentIdentifier,
        rpm: Option<Quota>,
        tpm: Option<Quota>,
    ) -> PyResult<()> {
        let er = self.embedding_router.clone();
        er.deploy(group, model_identifier, rpm, tpm)
            .into_pyresult()?;
        Ok(())
    }

    #[pyo3(signature = (group, model_identifier, rpm = None, tpm = None))]
    /// Adds a reranker model to the specified group.
    ///
    /// Registers a new model identifier within a specific routing group for reranking tasks.
    ///
    /// Args:
    ///     group (str): The target router group name.
    ///     model_identifier (str): The unique identifier of the model to be added.
    ///     rpm (Optional[Quota]): Optional requests per minute limit.
    ///     tpm (Optional[Quota]): Optional tokens per minute limit.
    ///
    /// Returns:
    ///     None: This is an asynchronous operation that modifies the router state.
    pub fn add_reranker_model(
        &self,
        group: RouteGroupName,
        model_identifier: DeploymentIdentifier,
        rpm: Option<Quota>,
        tpm: Option<Quota>,
    ) -> PyResult<()> {
        let rr = self.reranker_router.clone();
        rr.deploy(group, model_identifier, rpm, tpm)
            .into_pyresult()?;
        Ok(())
    }

    pub fn add_or_update_dummy_completion_model(
        &self,
        group: RouteGroupName,
        model_identifier: DeploymentIdentifier,
        responses: Vec<String>,
    ) -> PyResult<()> {
        if self
            .completion_router
            .remove_deployment(group.as_str(), model_identifier.clone())
            .is_ok()
        {
            debug!("Removed existing deployment for {:?}", model_identifier)
        }

        let (provider_name, model_name) = analyze_identifier(model_identifier).into_pyresult()?;
        let provider = self
            .completion_router
            .get_provider(provider_name)
            .into_pyresult()?;

        let dummy_model =
            DummyModel::new(model_name, provider).with_completion_responses(responses);

        let deployment = Deployment::new(Box::new(dummy_model) as Box<dyn CompletionModel>);

        self.completion_router
            .add_deployment(group, deployment)
            .into_pyresult()?;
        Ok(())
    }
}

/// Adds providers to a router from configuration.
///
/// Args:
///     router: The router to add providers to.
///     configs: A list of provider configurations.
///
/// Returns:
///     The router with providers added.
pub fn add_providers_from_configs<T: ModelTypeTag>(
    router: ThrydRouter<T>,
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

        router.add_or_update_provider(p);
    }

    Ok(router)
}

/// Adds models to a router from configuration.
///
/// Args:
///     router: The router to add models to.
///     configs: A list of deployment configurations.
///
/// Returns:
///     The router with models added.
pub fn add_models_from_configs<T: ModelTypeTag>(
    router: ThrydRouter<T>,
    configs: Vec<DeploymentConfig>,
) -> PyResult<ThrydRouter<T>> {
    for config in configs {
        router
            .deploy(config.group, config.id, config.rpm, config.tpm)
            .into_pyresult()?;
    }
    Ok(router)
}

/// Initializes a Router from a configuration object.
///
/// This function creates both embedding and completion routers from the config,
/// loading providers and models from the configured paths.
///
/// Args:
///     config: The configuration object containing routing settings.
///
/// Returns:
///     A new Router instance configured according to the config.
pub fn init_router_from_config() -> PyResult<Router> {
    trace!("Initializing router from config");
    let (cr, er, rr) = if let Some(p) = fabricatio_config::CONFIG
        .routing
        .cache_database_path
        .as_ref()
    {
        trace!("Mounting cache databases at {}", p.display());
        fs::create_dir_all(p).into_pyresult()?;
        (
            ThrydRouter::with_cache(p.join("completions")).into_pyresult()?,
            ThrydRouter::with_cache(p.join("embeddings")).into_pyresult()?,
            ThrydRouter::with_cache(p.join("rankings")).into_pyresult()?,
        )
    } else {
        (
            ThrydRouter::default(),
            ThrydRouter::default(),
            ThrydRouter::default(),
        )
    };
    let cr = add_providers_from_configs(cr, fabricatio_config::CONFIG.routing.providers.clone())?;
    let cr = add_models_from_configs(
        cr,
        fabricatio_config::CONFIG
            .routing
            .completion_deployments
            .clone(),
    )?;

    let er = add_providers_from_configs(er, fabricatio_config::CONFIG.routing.providers.clone())?;
    let er = add_models_from_configs(
        er,
        fabricatio_config::CONFIG
            .routing
            .embedding_deployments
            .clone(),
    )?;

    Ok(Router::new(er, cr, rr))
}

/// Counts the number of tokens in a text string.
///
/// This function uses the thryd library's token counting mechanism.
///
/// Args:
///     text: The input text to count tokens in.
///
/// Returns:
///     The number of tokens in the text.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
pub fn tokens_of(text: String) -> u64 {
    thryd::count_token(text)
}
