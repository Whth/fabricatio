use fabricatio_constants::ROUTER_VARNAME;
use futures_util::future::try_join_all;
use once_cell::sync::Lazy;
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use serde_json::to_value;
use std::error::Error;
use std::sync::Arc;
use strum::{AsRefStr, Display, EnumIter, EnumString};
use thryd::provider::{HeaderMap, Provider, Url};
use thryd::{
    Embedding, EmbeddingModel, EmbeddingRequest, Embeddings, Model, ModelName, Ranking,
    RerankerModel, RerankerRequest, ThrydError, async_trait,
};

struct TEI {
    name: String,
    url: Url,
}

#[derive(Debug, Clone, Copy, Display, AsRefStr, EnumString, EnumIter)]
pub enum TEIRoute {
    #[strum(serialize = "embed")]
    Embed,
    #[strum(serialize = "rerank")]
    Rerank,
}

#[derive(Serialize)]
pub struct TEIEmbeddingRequest {
    inputs: String,
}
#[derive(Deserialize)]
pub struct TEIEmbeddingResponse {
    embeddings: Embedding,
}

#[derive(Serialize)]
pub struct TEIRerankRequest {
    query: String,
    texts: Vec<String>,
}

#[derive(Deserialize)]
struct TEIRank {
    index: usize,
    score: f32,
}

#[derive(Deserialize)]
pub struct TEIRerankResponse {
    ranks: Vec<TEIRank>,
}

struct TEIModel {
    provider: Arc<dyn Provider>,
    name: String,
}

impl Model for TEIModel {
    fn model_name(&self) -> &str {
        self.name.as_str()
    }

    fn provider(&self) -> Arc<dyn Provider> {
        self.provider.clone()
    }
}

#[async_trait]
impl EmbeddingModel for TEIModel {
    async fn embedding(&self, request: EmbeddingRequest) -> thryd::Result<Embeddings> {
        try_join_all(request.texts.into_iter().map(async move |text| {
            let r = self
                .provider
                .post(
                    TEIRoute::Embed.as_ref(),
                    &to_value(TEIEmbeddingRequest { inputs: text }).unwrap(),
                )
                .await?
                .json::<TEIEmbeddingResponse>()
                .await?
                .embeddings;
            Ok(r)
        }))
        .await
        .map_err(|e: Box<dyn Error + Send + Sync>| ThrydError::Router(e.to_string()))
    }
}
#[async_trait]
impl RerankerModel for TEIModel {
    async fn rerank(&self, request: RerankerRequest) -> thryd::Result<Ranking> {
        let req = TEIRerankRequest {
            query: request.query,
            texts: request.documents,
        };
        let r = self
            .provider
            .post(TEIRoute::Rerank.as_ref(), &to_value(req)?)
            .await?
            .json::<TEIRerankResponse>()
            .await?
            .ranks
            .into_iter()
            .map(|rank| (rank.index, rank.score))
            .collect();

        Ok(r)
    }
}

impl Provider for TEI {
    fn provider_name(&self) -> &str {
        self.name.as_str()
    }

    fn endpoint(&self) -> Url {
        self.url.clone()
    }

    fn headers(&self) -> thryd::Result<HeaderMap> {
        Ok(HeaderMap::new())
    }

    fn create_embedding_model(
        self: Arc<Self>,
        model_name: ModelName,
    ) -> thryd::Result<Box<dyn EmbeddingModel>> {
        Ok(Box::new(TEIModel {
            provider: self.clone(),
            name: model_name.to_string(),
        }))
    }

    fn create_reranker_model(
        self: Arc<Self>,
        model_name: ModelName,
    ) -> thryd::Result<Box<dyn RerankerModel>> {
        Ok(Box::new(TEIModel {
            provider: self.clone(),
            name: model_name.to_string(),
        }))
    }
}

#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

/// Cached Router reference. Extracted once via Python module lookup.
static ROUTER: Lazy<fabricatio_core::Router> = Lazy::new(|| {
    Python::with_gil(|py| {
        let module = py.import_bound("fabricatio_core.rust").unwrap();
        module
            .getattr(ROUTER_VARNAME)
            .unwrap()
            .extract()
            .map_err(|e: pyo3::PyErr| format!("Failed to extract Router: {e}"))
            .unwrap()
    })
});

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn add_tei(name: String, url: String) -> PyResult<()> {
    use pyo3::exceptions::PyValueError;

    let router = &*ROUTER;

    let url: Url = url
        .parse()
        .map_err(|e| PyValueError::new_err(e.to_string()))?;

    let tei = Arc::new(TEI { name, url });
    router.embedding_router.add_or_update_provider(tei.clone());
    router.reranker_router.add_or_update_provider(tei);

    Ok(())
}

pub(crate) fn register(py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(add_tei, m)?)?;
    Ok(())
}
