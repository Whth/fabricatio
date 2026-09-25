use error_mapping::AsPyErr;
use fabricatio_config::{DeploymentConfig, ProviderConfig, SecretStr};
use fabricatio_logger::{debug, error, trace};
use futures::FutureExt;
use futures::future::join_all;
pub use image::attach;
use jevlin::{Choice, ChoiceCriteria, Noul, NoulCriteria, Question, Score, ScoreCriteria};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use pyo3_stub_gen::derive::*;
use std::collections::BTreeMap;
use std::fs;
use std::sync::Arc;
use thryd::deployment::Deployment;
use thryd::tracker::Quota;
pub use thryd::utils::analyze_identifier;
use thryd::{
    CompletionModel, CompletionTag, CompletionText, DeploymentIdentifier, DummyModel, Embedding,
    EmbeddingModel, EmbeddingRequest, EmbeddingTag, EvaluationAnswer, EvaluationModel,
    EvaluationRequest, EvaluationResponse, EvaluationTag, ModelTypeTag, RankedDocuments,
    RerankerModel, RerankerRequest, RerankerTag, RetryConfig, Router as ThrydRouter,
    create_provider,
};

mod image;

pub use thryd::{CachePolicy, CompletionRequest, ImageAttachment, ProviderType, RouteGroupName};
/// The id a single-question evaluation files its question under.
///
/// The answer comes back under the same id, which is all the API needs of it: the id is never sent
/// to the model and never reaches a caller either, because the router reads the only answer it gets.
const ANSWER_ID: &str = "answer";

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(from_py_object)]
#[derive(Default, Clone)]
pub struct Router {
    pub embedding_router: Arc<ThrydRouter<EmbeddingTag>>,
    pub completion_router: Arc<ThrydRouter<CompletionTag>>,
    pub reranker_router: Arc<ThrydRouter<RerankerTag>>,
    pub evaluation_router: Arc<ThrydRouter<EvaluationTag>>,
}

impl Router {
    pub fn new(
        embedding_router: ThrydRouter<EmbeddingTag>,
        completion_router: ThrydRouter<CompletionTag>,
        reranker_router: ThrydRouter<RerankerTag>,
        evaluation_router: ThrydRouter<EvaluationTag>,
    ) -> Self {
        Self {
            embedding_router: Arc::new(embedding_router),
            completion_router: Arc::new(completion_router),
            reranker_router: Arc::new(reranker_router),
            evaluation_router: Arc::new(evaluation_router),
        }
    }

    pub async fn embedding_rs(
        self,
        send_to: RouteGroupName,
        req: EmbeddingRequest,
        policy: CachePolicy,
    ) -> PyResult<Vec<Embedding>> {
        Self::embedding_inner(send_to, req, self.embedding_router.clone(), policy).await
    }

    pub async fn embedding_inner(
        send_to: RouteGroupName,
        req: EmbeddingRequest,
        r: Arc<ThrydRouter<EmbeddingTag>>,
        policy: CachePolicy,
    ) -> PyResult<Vec<Embedding>> {
        r.invoke(send_to.clone(), req, policy)
            .await
            .into_pyresult()
            .map(|e| e.embeddings)
    }
    pub async fn rerank_inner(
        send_to: RouteGroupName,
        req: RerankerRequest,
        r: Arc<ThrydRouter<RerankerTag>>,
        policy: CachePolicy,
    ) -> PyResult<RankedDocuments> {
        r.invoke(send_to.clone(), req, policy)
            .await
            .into_pyresult()
            .map(|r| r.rankings)
    }

    /// Answers one question about a state, and returns the whole response.
    ///
    /// The response carries the model that answered, the answer to the one question asked, and the
    /// tokens it cost — everything a caller needs to record what an evaluation said and what it
    /// came from.
    pub async fn evaluation_inner(
        send_to: RouteGroupName,
        req: EvaluationRequest,
        r: Arc<ThrydRouter<EvaluationTag>>,
        policy: CachePolicy,
    ) -> PyResult<EvaluationResponse> {
        r.invoke(send_to, req, policy).await.into_pyresult()
    }

    /// Bundles one question into the request that asks it, under the id a single question needs.
    ///
    /// The state travels as the text the caller wrote, and the question is one of the three typed
    /// questions the API takes, so nothing here reads a caller's text into a request. Which model
    /// answers is the deployment's business: a request that names none takes the model name of the
    /// deployment the router picks, as it does for the other modalities.
    fn evaluation_request(state: String, question: Question) -> EvaluationRequest {
        EvaluationRequest::new(state).with_question(ANSWER_ID, question)
    }

    /// Answers a one-question evaluation, and returns the one answer it came back with.
    ///
    /// One question was asked, so exactly one answer is expected: it is taken as it is, and a
    /// response holding none or several is refused rather than guessed at.
    async fn evaluation_answer(
        send_to: RouteGroupName,
        request: EvaluationRequest,
        r: Arc<ThrydRouter<EvaluationTag>>,
        policy: CachePolicy,
    ) -> PyResult<EvaluationAnswer> {
        let response = Self::evaluation_inner(send_to, request, r, policy).await?;
        let mut answers = response.answers.into_values();
        let answer = answers.next().ok_or_else(|| {
            PyValueError::new_err(
                "the evaluation came back without an answer, but one question was asked",
            )
        })?;
        if answers.next().is_some() {
            return Err(PyValueError::new_err(
                "the evaluation came back with more than one answer, but one question was asked",
            ));
        }
        Ok(answer)
    }
    pub async fn completion_batch_rs(
        &self,
        send_to: RouteGroupName,
        reqs: Vec<CompletionRequest>,
        policy: CachePolicy,
    ) -> Vec<Option<String>> {
        Self::completion_batch_inner(send_to, reqs, self.completion_router.clone(), policy).await
    }

    pub async fn completion_batch_inner(
        send_to: RouteGroupName,
        reqs: Vec<CompletionRequest>,
        r: Arc<ThrydRouter<CompletionTag>>,
        policy: CachePolicy,
    ) -> Vec<Option<String>> {
        join_all(
            reqs.into_iter()
                .map(|req| r.invoke(send_to.clone(), req, policy)),
        )
        .map(|results| {
            results
                .into_iter()
                .map(|res| {
                    if res.is_ok() {
                        res.ok().map(|c| c.content)
                    } else {
                        error!("Error in completion batch: {:?}", res);
                        None
                    }
                })
                .collect::<Vec<Option<String>>>()
        })
        .await
    }

    pub async fn completion_rs(
        self,
        send_to: RouteGroupName,
        req: CompletionRequest,
    ) -> PyResult<String> {
        Self::completion_inner(
            send_to,
            req,
            self.completion_router.clone(),
            CachePolicy::CACHED,
        )
        .await
    }
    pub async fn completion_inner(
        send_to: RouteGroupName,
        req: CompletionRequest,
        r: Arc<ThrydRouter<CompletionTag>>,
        policy: CachePolicy,
    ) -> PyResult<String> {
        r.invoke(send_to, req, policy)
            .await
            .into_pyresult()
            .map(|c| c.content)
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
    #[pyo3(signature = (send_to, message, stream = false, top_p=None, temperature=None, max_completion_tokens = None, presence_penalty = None, frequency_penalty = None, effort = None, no_cache = false, no_store = false, images = None)
    )]
    /// Sends a completion request to the specified group and returns the full response.
    ///
    /// When `images` is non-empty, raw bytes are auto-detected for MIME type and
    /// base64-encoded into data URIs for multimodal requests. With `[routing.image_compression]`
    /// enabled the payload is a lossy re-encode at the configured quality and format instead;
    /// the completion cache keys on the digest of the original bytes either way, so cache
    /// hits do not depend on the compression settings.
    ///
    /// Args:
    ///     send_to (str): The router group name.
    ///     message (str): The user prompt content.
    ///     stream (bool): Logical flag for compatibility. Defaults to False.
    ///     top_p (Optional[float]): Nucleus sampling parameter. Defaults to 1.0 if None.
    ///     temperature (Optional[float]): Controls randomness. Defaults to 0.7 if None.
    ///     max_completion_tokens (Optional[int]): Maximum tokens to generate. Defaults to 2048 if None.
    ///     presence_penalty (Optional[float]): Penalizes new tokens based on presence. Defaults to 0.0 if None.
    ///     frequency_penalty (Optional[float]): Penalizes new tokens based on frequency. Defaults to 0.0 if None.
    ///     effort (Optional[str]): Reasoning effort for models that support it (e.g. "low", "medium", "high"). Defaults to None.
    ///     no_cache (bool): Whether to bypass the cache read for this request. Defaults to False.
    ///     no_store (bool): Whether to skip persisting the response. Defaults to False.
    ///     images (List[bytes]): Optional raw image bytes for multimodal requests. Defaults to empty.
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
        effort: Option<String>,
        no_cache: bool,
        no_store: bool,
        #[gen_stub(override_type(type_repr = "list[bytes] | None"))] images: Option<Vec<Vec<u8>>>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let req = CompletionRequest {
            message,
            top_p,
            temperature,
            stream,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
            effort,
            images: images
                .unwrap_or_default()
                .into_iter()
                .map(|b| crate::image::attach(&b))
                .collect(),
        };

        let r = self.completion_router.clone();

        future_into_py(python, async move {
            Self::completion_inner(send_to, req, r, CachePolicy::new(no_cache, no_store)).await
        })
    }

    #[allow(clippy::too_many_arguments)]
    #[pyo3(signature = (send_to, messages, stream = false, top_p=None, temperature=None, max_completion_tokens = None, presence_penalty = None, frequency_penalty = None, effort = None, no_cache = false, no_store = false, images = None)
    )]
    /// Sends a batch of completion requests to the specified group and returns all responses.
    ///
    /// When `images` is non-empty, all images are broadcast to every message. Each is
    /// prepared exactly as in `completion`: lossily re-encoded when `[routing.image_compression]`
    /// is enabled, cached under the digest of the original bytes.
    ///
    /// Args:
    ///     send_to (str): The router group name.
    ///     messages (List[str]): A list of user prompt contents.
    ///     stream (bool): Logical flag for compatibility. Defaults to False.
    ///     top_p (Optional[float]): Nucleus sampling parameter. Defaults to 1.0 if None.
    ///     temperature (Optional[float]): Controls randomness. Defaults to 0.7 if None.
    ///     max_completion_tokens (Optional[int]): Maximum tokens to generate. Defaults to 2048 if None.
    ///     presence_penalty (Optional[float]): Penalizes new tokens based on presence. Defaults to 0.0 if None.
    ///     frequency_penalty (Optional[float]): Penalizes new tokens based on frequency. Defaults to 0.0 if None.
    ///     effort (Optional[str]): Reasoning effort for models that support it (e.g. "low", "medium", "high"). Defaults to None.
    ///     no_cache (bool): Whether to bypass the cache read for each request. Defaults to False.
    ///     no_store (bool): Whether to skip persisting each response. Defaults to False.
    ///     images (List[bytes]): Optional raw image bytes broadcast to all messages. Defaults to empty.
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
        effort: Option<String>,
        no_cache: bool,
        no_store: bool,
        #[gen_stub(override_type(type_repr = "list[bytes] | None"))] images: Option<Vec<Vec<u8>>>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let attachments: Vec<ImageAttachment> = images
            .unwrap_or_default()
            .into_iter()
            .map(|b| crate::image::attach(&b))
            .collect();
        let reqs = if attachments.is_empty() {
            messages
                .into_iter()
                .map(|message| CompletionRequest {
                    message,
                    top_p,
                    temperature,
                    stream,
                    max_completion_tokens,
                    presence_penalty,
                    frequency_penalty,
                    effort: effort.clone(),
                    images: vec![],
                })
                .collect::<Vec<_>>()
        } else {
            // All messages get the same image set
            messages
                .into_iter()
                .map(|message| CompletionRequest {
                    message,
                    stream,
                    top_p,
                    temperature,
                    max_completion_tokens,
                    presence_penalty,
                    frequency_penalty,
                    effort: effort.clone(),
                    images: attachments.clone(),
                })
                .collect::<Vec<_>>()
        };
        let r = self.completion_router.clone();
        future_into_py(python, async move {
            Ok(
                Self::completion_batch_inner(
                    send_to,
                    reqs,
                    r,
                    CachePolicy::new(no_cache, no_store),
                )
                .await,
            )
        })
    }

    #[allow(clippy::too_many_arguments)]
    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[typing.List[typing.List[float]]]", imports = ("typing",)
        )
    )]
    /// Sends an embedding request to the specified group.
    ///
    /// Args:
    ///     send_to (str): The router group name to route the embedding request.
    ///     texts (List[str]): A list of text strings to generate embeddings for.
    ///     ndim (int): The dimensionality of the output embeddings. Must match between search and store.
    ///     max_batch_emb_size (Optional[int]): Maximum texts per API call. When exceeded, the batch is
    ///         split into chunks and fanned out in parallel. Defaults to None (no chunking).
    ///     no_cache (bool): Whether to bypass the cache read for this request. Defaults to False.
    ///     no_store (bool): Whether to skip persisting the response. Defaults to False.
    ///
    /// Returns:
    ///     List[List[float]]: A list of embedding vectors corresponding to the input texts.
    #[pyo3(signature = (send_to, texts, ndim, no_cache = false, no_store = false, max_batch_emb_size = None))]
    pub fn embedding<'a>(
        &self,
        python: Python<'a>,
        send_to: RouteGroupName,
        texts: Vec<String>,
        ndim: u32,
        no_cache: bool,
        no_store: bool,
        max_batch_emb_size: Option<usize>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let r = self.embedding_router.clone();

        future_into_py(python, async move {
            Self::embedding_inner(
                send_to,
                EmbeddingRequest {
                    texts,
                    ndim,
                    max_batch_emb_size,
                },
                r,
                CachePolicy::new(no_cache, no_store),
            )
            .await
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
    ///     no_cache (bool): Whether to bypass the cache read for this request. Defaults to False.
    ///     no_store (bool): Whether to skip persisting the response. Defaults to False.
    ///
    /// Returns:
    ///     List[Tuple[int, float]]: A list of (document_index, score) pairs sorted by relevance descending.
    #[pyo3(signature = (send_to, query, documents, no_cache = false, no_store = false))]
    pub fn rerank<'a>(
        &self,
        python: Python<'a>,
        send_to: RouteGroupName,
        query: String,
        documents: Vec<String>,
        no_cache: bool,
        no_store: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let r = self.reranker_router.clone();
        let req = RerankerRequest { query, documents };
        future_into_py(python, async move {
            Self::rerank_inner(send_to, req, r, CachePolicy::new(no_cache, no_store)).await
        })
    }

    #[allow(clippy::too_many_arguments)]
    #[gen_stub(override_return_type(type_repr = "typing.Awaitable[bool]", imports = ("typing",)))]
    #[pyo3(signature = (send_to, state, field, affirm_case = None, deny_case = None, no_cache = false, no_store = false))]
    /// Judges a state against one yes/no question, and answers it with a verdict.
    ///
    /// A judgement is binary here: a probability of yes at or above one half is a yes, anything
    /// below it a no. `affirm_case` and `deny_case` say what each side means when the question
    /// alone would be ambiguous.
    ///
    /// Args:
    ///     send_to (str): The evaluation route group to send the request to.
    ///     state (str): The text to judge.
    ///     field (str): The yes/no question to judge the state against.
    ///     affirm_case (Optional[str]): What a yes means, when that needs saying.
    ///     deny_case (Optional[str]): What a no means, when that needs saying.
    ///     no_cache (bool): Whether to bypass the cache read for this request. Defaults to False.
    ///     no_store (bool): Whether to skip persisting the response. Defaults to False.
    ///
    /// Returns:
    ///     bool: The verdict.
    pub fn evaluate_verdict<'a>(
        &self,
        python: Python<'a>,
        send_to: RouteGroupName,
        state: String,
        field: String,
        affirm_case: Option<String>,
        deny_case: Option<String>,
        no_cache: bool,
        no_store: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let mut criteria = NoulCriteria::new();
        if let Some(affirm_case) = affirm_case {
            criteria = criteria.with_yes(affirm_case);
        }
        if let Some(deny_case) = deny_case {
            criteria = criteria.with_no(deny_case);
        }
        let question = if criteria.is_empty() {
            Noul::new(field)
        } else {
            Noul::new(field).with_criteria(criteria)
        };
        let request = Self::evaluation_request(state, Question::Noul(question));
        let r = self.evaluation_router.clone();

        future_into_py(python, async move {
            let answer =
                Self::evaluation_answer(send_to, request, r, CachePolicy::new(no_cache, no_store))
                    .await?;
            let noul = answer.as_noul().ok_or_else(|| {
                PyValueError::new_err("a yes/no question was answered with another kind of answer")
            })?;
            Ok(noul.noul >= 0.5)
        })
    }

    #[allow(clippy::too_many_arguments)]
    #[gen_stub(override_return_type(type_repr = "typing.Awaitable[str]", imports = ("typing",)))]
    #[pyo3(signature = (send_to, state, field, candidates, no_cache = false, no_store = false))]
    /// Picks one of `candidates` for a state, and answers it with the one it picked.
    ///
    /// Every candidate carries the rubric that says when it applies, or `None` when its name
    /// speaks for itself. The answer is the candidate itself, not the distribution behind it.
    ///
    /// Args:
    ///     send_to (str): The evaluation route group to send the request to.
    ///     state (str): The text to pick for.
    ///     field (str): What the model should decide.
    ///     candidates (dict[str, str | None]): Every option, mapped to the rubric that describes
    ///         when it applies, or `None` when it needs no extra detail.
    ///     no_cache (bool): Whether to bypass the cache read for this request. Defaults to False.
    ///     no_store (bool): Whether to skip persisting the response. Defaults to False.
    ///
    /// Returns:
    ///     str: The candidate the model picked.
    pub fn evaluate_choice<'a>(
        &self,
        python: Python<'a>,
        send_to: RouteGroupName,
        state: String,
        field: String,
        candidates: BTreeMap<String, Option<String>>,
        no_cache: bool,
        no_store: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let mut criteria = ChoiceCriteria::new();
        for (candidate, rubric) in candidates {
            criteria = match rubric {
                Some(rubric) => criteria.with_option(candidate, rubric),
                None => criteria.with_bare_option(candidate),
            };
        }
        let question = Choice::new(field, criteria).into_pyresult()?;
        let request = Self::evaluation_request(state, Question::Choice(question));
        let r = self.evaluation_router.clone();

        future_into_py(python, async move {
            let answer =
                Self::evaluation_answer(send_to, request, r, CachePolicy::new(no_cache, no_store))
                    .await?;
            let choice = answer.as_choice().ok_or_else(|| {
                PyValueError::new_err(
                    "a pick-one question was answered with another kind of answer",
                )
            })?;
            Ok(choice.choice.clone())
        })
    }

    #[allow(clippy::too_many_arguments)]
    #[gen_stub(override_return_type(type_repr = "typing.Awaitable[dict[str, float]]", imports = ("typing",)))]
    #[pyo3(signature = (send_to, state, field, criteria, no_cache = false, no_store = false))]
    /// Rates a state over an ordered set of levels, and answers with the levels and their weights.
    ///
    /// The levels run from the lowest to the highest, and the answer maps every one of them back
    /// to the probability the model gave it, so a rating that lands between two levels shows as
    /// weight on both rather than as a single value the caller has to interpret.
    ///
    /// Args:
    ///     send_to (str): The evaluation route group to send the request to.
    ///     state (str): The text to rate.
    ///     field (str): What the model should rate.
    ///     criteria (List[str]): The levels, lowest first, between two and ten of them.
    ///     no_cache (bool): Whether to bypass the cache read for this request. Defaults to False.
    ///     no_store (bool): Whether to skip persisting the response. Defaults to False.
    ///
    /// Returns:
    ///     dict[str, float]: Every level, mapped to the probability the model gave it.
    pub fn evaluate_rating<'a>(
        &self,
        python: Python<'a>,
        send_to: RouteGroupName,
        state: String,
        field: String,
        criteria: Vec<String>,
        no_cache: bool,
        no_store: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let mut levels = ScoreCriteria::new();
        for level in criteria {
            levels = levels.with_level(level);
        }
        let question = Score::new(field, levels).into_pyresult()?;
        let request = Self::evaluation_request(state, Question::Score(question));
        let r = self.evaluation_router.clone();

        future_into_py(python, async move {
            let answer =
                Self::evaluation_answer(send_to, request, r, CachePolicy::new(no_cache, no_store))
                    .await?;
            let score = answer.as_score().ok_or_else(|| {
                PyValueError::new_err("a rating question was answered with another kind of answer")
            })?;
            let mut indices = score
                .probabilities
                .keys()
                .map(|index| {
                    index.parse::<usize>().map_err(|_| {
                        PyValueError::new_err(format!(
                            "the rating came back about a level that is not a number: {index}"
                        ))
                    })
                })
                .collect::<PyResult<Vec<usize>>>()?;
            indices.sort_unstable();
            let mut rated = BTreeMap::new();
            for index in indices {
                let level = score.level(index).ok_or_else(|| {
                    PyValueError::new_err(format!(
                        "the rating came back about level {index} without naming it"
                    ))
                })?;
                rated.insert(level.to_string(), score.probabilities[&index.to_string()]);
            }
            Ok(rated)
        })
    }

    #[pyo3(signature = (provider_type, name = None, api_key = None, endpoint = None))]
    /// Adds a provider to the router.
    ///
    /// This method registers a new provider with the completion, embedding, reranker, and
    /// evaluation routers.
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
        let jr = self.evaluation_router.clone();

        cr.add_or_update_provider(p.clone());
        er.add_or_update_provider(p.clone());
        rr.add_or_update_provider(p.clone());
        jr.add_or_update_provider(p);
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

    #[pyo3(signature = (group, model_identifier, rpm = None, tpm = None))]
    /// Adds an evaluation model to the specified group.
    ///
    /// Registers a new model identifier within a specific routing group for evaluations. The
    /// provider that backs it must support evaluations — TypeSafe's Jev does.
    ///
    /// Args:
    ///     group (str): The target router group name.
    ///     model_identifier (str): The unique identifier of the model to be added.
    ///     rpm (Optional[Quota]): Optional requests per minute limit.
    ///     tpm (Optional[Quota]): Optional tokens per minute limit.
    ///
    /// Returns:
    ///     None: This is an asynchronous operation that modifies the router state.
    pub fn add_evaluation_model(
        &self,
        group: RouteGroupName,
        model_identifier: DeploymentIdentifier,
        rpm: Option<Quota>,
        tpm: Option<Quota>,
    ) -> PyResult<()> {
        let jr = self.evaluation_router.clone();
        jr.deploy(group, model_identifier, rpm, tpm)
            .into_pyresult()?;
        Ok(())
    }

    pub fn add_or_update_dummy_completion_model(
        &self,
        group: RouteGroupName,
        model_identifier: DeploymentIdentifier,
        responses: Vec<CompletionText>,
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

    pub fn add_or_update_dummy_embedding_model(
        &self,
        group: RouteGroupName,
        model_identifier: DeploymentIdentifier,
        embeddings: Vec<Vec<Embedding>>,
    ) -> PyResult<()> {
        if self
            .embedding_router
            .remove_deployment(group.as_str(), model_identifier.clone())
            .is_ok()
        {
            debug!("Removed existing deployment for {:?}", model_identifier)
        }

        let (provider_name, model_name) = analyze_identifier(model_identifier).into_pyresult()?;
        let provider = self
            .embedding_router
            .get_provider(provider_name)
            .into_pyresult()?;

        let dummy_model =
            DummyModel::new(model_name, provider).with_embedding_responses(embeddings);

        let deployment = Deployment::new(Box::new(dummy_model) as Box<dyn EmbeddingModel>);

        self.embedding_router
            .add_deployment(group, deployment)
            .into_pyresult()?;
        Ok(())
    }
    pub fn add_or_update_dummy_reranker_model(
        &self,
        group: RouteGroupName,
        model_identifier: DeploymentIdentifier,
        rankings: Vec<RankedDocuments>,
    ) -> PyResult<()> {
        if self
            .reranker_router
            .remove_deployment(group.as_str(), model_identifier.clone())
            .is_ok()
        {
            debug!("Removed existing deployment for {:?}", model_identifier)
        }

        let (provider_name, model_name) = analyze_identifier(model_identifier).into_pyresult()?;
        let provider = self
            .reranker_router
            .get_provider(provider_name)
            .into_pyresult()?;

        let dummy_model = DummyModel::new(model_name, provider).with_reranker_responses(rankings);

        let deployment = Deployment::new(Box::new(dummy_model) as Box<dyn RerankerModel>);

        self.reranker_router
            .add_deployment(group, deployment)
            .into_pyresult()?;
        Ok(())
    }

    /// Seeds a dummy evaluation model with scripted responses.
    ///
    /// Each response is a whole evaluation response as JSON — the model that answered, the
    /// answers under their ids, and the usage — so a test declares what the model says, not just
    /// how many answers it gives. The dummy model hands responses back last-in-first-out, as the
    /// models of the other modalities do; the Python seeding helpers reverse them so a test reads
    /// them in the order it gave them.
    ///
    /// Args:
    ///     group (str): The target router group name.
    ///     model_identifier (str): The unique identifier of the model, as `provider/model`.
    ///     responses (List[str]): The evaluation responses, each a JSON document.
    ///
    /// Returns:
    ///     None: This is an asynchronous operation that modifies the router state.
    pub fn add_or_update_dummy_evaluation_model(
        &self,
        group: RouteGroupName,
        model_identifier: DeploymentIdentifier,
        responses: Vec<String>,
    ) -> PyResult<()> {
        if self
            .evaluation_router
            .remove_deployment(group.as_str(), model_identifier.clone())
            .is_ok()
        {
            debug!("Removed existing deployment for {:?}", model_identifier)
        }

        let (provider_name, model_name) = analyze_identifier(model_identifier).into_pyresult()?;
        let provider = self
            .evaluation_router
            .get_provider(provider_name)
            .into_pyresult()?;

        let responses = responses
            .into_iter()
            .map(|response| serde_json::from_str::<EvaluationResponse>(&response).into_pyresult())
            .collect::<PyResult<Vec<_>>>()?;

        let dummy_model =
            DummyModel::new(model_name, provider).with_evaluation_responses(responses);

        let deployment = Deployment::new(Box::new(dummy_model) as Box<dyn EvaluationModel>);

        self.evaluation_router
            .add_deployment(group, deployment)
            .into_pyresult()?;
        Ok(())
    }

    /// Configures automatic retry for every sub-router: completion, embedding, reranker, and
    /// evaluation.
    ///
    /// When set, failed requests (network errors, timeouts, upstream 429/5xx) are retried with
    /// exponential backoff, waiting the delay a rate limit names when it names one.
    ///
    /// Args:
    ///     max_retries (int): Maximum retry attempts after initial failure. 0 disables retries.
    ///     initial_backoff_ms (int): Initial backoff duration in milliseconds. Defaults to 1000.
    ///     max_backoff_ms (int): Maximum backoff cap in milliseconds. Defaults to 30000.
    ///     backoff_multiplier (float): Exponential backoff multiplier. Defaults to 2.0.
    #[pyo3(signature = (max_retries, initial_backoff_ms = 1000, max_backoff_ms = 30000, backoff_multiplier = 2.0))]
    pub fn set_retry(
        &self,
        max_retries: u32,
        initial_backoff_ms: u64,
        max_backoff_ms: u64,
        backoff_multiplier: f64,
    ) {
        let config = if max_retries == 0 {
            None
        } else {
            Some(RetryConfig {
                max_retries,
                initial_backoff_ms,
                max_backoff_ms,
                backoff_multiplier,
            })
        };
        self.completion_router.set_retry(config.clone());
        self.embedding_router.set_retry(config.clone());
        self.reranker_router.set_retry(config.clone());
        self.evaluation_router.set_retry(config);
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
/// This function creates the embedding, completion, reranker, and evaluation routers from the
/// config, loading providers and models from the configured paths.
///
/// Args:
///     config: The configuration object containing routing settings.
///
/// Returns:
///     A new Router instance configured according to the config.
pub fn init_router_from_config() -> PyResult<Router> {
    trace!("Initializing router from config");
    let (cr, er, rr, jr) = if let Some(p) = fabricatio_config::CONFIG
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
            ThrydRouter::with_cache(p.join("evaluations")).into_pyresult()?,
        )
    } else {
        (
            ThrydRouter::default(),
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

    let rr = add_providers_from_configs(rr, fabricatio_config::CONFIG.routing.providers.clone())?;
    let rr = add_models_from_configs(
        rr,
        fabricatio_config::CONFIG
            .routing
            .reranker_deployments
            .clone(),
    )?;

    let jr = add_providers_from_configs(jr, fabricatio_config::CONFIG.routing.providers.clone())?;
    let jr = add_models_from_configs(
        jr,
        fabricatio_config::CONFIG
            .routing
            .evaluation_deployments
            .clone(),
    )?;

    // Apply retry config from settings if present, to every modality: a rate limit comes back
    // carrying the delay the API asked for, and the wait for it is the router's to take.
    let routing = &fabricatio_config::CONFIG.routing;
    let (cr, er, rr, jr) = if let Some(max_retries) = routing.retry_max_retries {
        let rc = RetryConfig {
            max_retries,
            initial_backoff_ms: routing.retry_initial_backoff_ms.unwrap_or(1000),
            max_backoff_ms: routing.retry_max_backoff_ms.unwrap_or(30_000),
            backoff_multiplier: routing.retry_backoff_multiplier.unwrap_or(2.0),
        };
        trace!(
            "Enabling retry: max_retries={}, backoff={}ms..{}ms x{}",
            rc.max_retries, rc.initial_backoff_ms, rc.max_backoff_ms, rc.backoff_multiplier
        );
        (
            cr.with_retry(rc.clone()),
            er.with_retry(rc.clone()),
            rr.with_retry(rc.clone()),
            jr.with_retry(rc),
        )
    } else {
        (cr, er, rr, jr)
    };

    Ok(Router::new(er, cr, rr, jr))
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
