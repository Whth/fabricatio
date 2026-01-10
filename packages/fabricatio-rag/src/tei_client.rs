use crate::tei::embed_client::EmbedClient;
use crate::tei::rerank_client::RerankClient;
use crate::tei::{EmbedAllRequest, EmbedRequest, RerankRequest, TruncationDirection};
use error_mapping::AsPyErr;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use pyo3_stub_gen::derive::{gen_stub_pyclass, gen_stub_pymethods};
use tonic::transport::Channel;

#[gen_stub_pyclass]
#[pyclass]
struct TEIClient {
    channel: Channel,
}

#[gen_stub_pymethods]
#[pymethods]
impl TEIClient {
    /// Creates a new TEI client connected to the specified base URL.
    ///
    /// # Arguments
    /// * `base_url` - The URL to connect to, e.g., "http://localhost:8080"
    ///
    /// # Returns
    /// An awaitable that resolves to a new TEIClient instance

    #[staticmethod]
    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[typing.Self]",imports=("typing",))
    )]
    fn connect<'a>(python: Python<'a>, base_url: String) -> PyResult<Bound<'a, PyAny>> {
        future_into_py(python, async move {
            let client = TEIClient {
                channel: Channel::from_shared(base_url)
                    .into_pyresult()?
                    .connect()
                    .await
                    .into_pyresult()?,
            };
            Ok(client)
        })
    }

    /// Reranks a list of texts based on their relevance to the given query.
    ///
    /// # Arguments
    /// * `query` - The query string to compare against
    /// * `texts` - A vector of text strings to rerank
    /// * `truncate` - Whether to truncate the input texts if they exceed the maximum length
    /// * `truncation_direction` - Direction of truncation, either "Left", "Right", or "None"
    ///
    /// # Returns
    /// An awaitable that resolves to a list of tuples containing the index and score of each text,
    /// sorted by relevance score in descending order
    #[pyo3(signature = (query, texts, truncate=false, truncation_direction="Left"))]
    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[typing.List[typing.Tuple[int, float]]",imports=("typing",)
        )
    )]
    fn arerank<'py>(
        &self,
        python: Python<'py>,
        query: String,
        texts: Vec<String>,
        truncate: bool,
        truncation_direction: &str,
    ) -> PyResult<Bound<'py, PyAny>> {
        let request = RerankRequest {
            query,
            texts,
            truncate,
            truncation_direction: truncation_direction
                .parse::<TruncationDirection>()
                .into_pyresult()?
                .into(),
            raw_scores: false,
            return_text: false,
        };
        let channel = self.channel.clone();
        // Send only non-Python data into the async block
        future_into_py(python, async move {
            Ok(RerankClient::new(channel)
                .rerank(request)
                .await
                .into_pyresult()?
                .into_inner()
                .ranks
                .into_iter()
                .map(|rank| (rank.index, rank.score))
                .collect::<Vec<(u32, f32)>>())
        })
    }
    #[pyo3(signature = ( text, truncate=false, truncation_direction="Left"))]
    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[typing.List[typing.List[float]]]",imports=("typing",)
        )
    )]
    fn embed_all<'py>(
        &self,
        python: Python<'py>,
        text: String,
        truncate: bool,

        truncation_direction: &str,
    ) -> PyResult<Bound<'py, PyAny>> {
        let req = EmbedAllRequest {
            inputs: text,
            truncate,

            truncation_direction: truncation_direction
                .parse::<TruncationDirection>()
                .into_pyresult()?
                .into(),
            prompt_name: None,
        };

        let channel = self.channel.clone();
        // Send only non-Python data into the async block
        future_into_py(python, async move {
            Ok(EmbedClient::new(channel)
                .embed_all(req)
                .await
                .into_pyresult()?
                .into_inner()
                .token_embeddings
                .into_iter()
                .map(|embedding| embedding.embeddings)
                .collect::<Vec<Vec<f32>>>())
        })
    }

    /// Generates embeddings for the given text.
    ///
    /// # Arguments
    /// * `text` - The input text to generate embeddings for
    /// * `dimensions` - Optional parameter to specify the number of dimensions in the output embeddings
    /// * `truncate` - Whether to truncate the input text if it exceeds the maximum length
    /// * `truncation_direction` - Direction of truncation, either "Left", "Right", or "None"
    ///
    /// # Returns
    /// An awaitable that resolves to a list of floats representing the embeddings
    #[pyo3(signature = ( text,dimensions=None, truncate=false, truncation_direction="Left"))]
    #[gen_stub(
        override_return_type(type_repr = "typing.Awaitable[typing.List[float]]",imports=("typing",)
        )
    )]
    fn embed<'py>(
        &self,
        python: Python<'py>,
        text: String,
        dimensions: Option<u32>,
        truncate: bool,
        truncation_direction: &str,
    ) -> PyResult<Bound<'py, PyAny>> {
        let req = EmbedRequest {
            inputs: text,
            normalize: false,
            truncate,
            truncation_direction: truncation_direction
                .parse::<TruncationDirection>()
                .into_pyresult()?
                .into(),
            prompt_name: None,
            dimensions,
        };

        let channel = self.channel.clone();
        // Send only non-Python data into the async block
        future_into_py(python, async move {
            Ok(EmbedClient::new(channel)
                .embed(req)
                .await
                .into_pyresult()?
                .into_inner()
                .embeddings)
        })
    }
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TEIClient>()?;
    Ok(())
}
