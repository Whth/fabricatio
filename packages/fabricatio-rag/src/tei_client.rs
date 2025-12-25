use crate::tei::rerank_client::RerankClient;
use crate::tei::{RerankRequest, TruncationDirection};
use error_mapping::AsPyErr;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use tokio::sync::OnceCell;
use tonic::transport::Channel;
use validator::Validate;

#[pyclass]
#[derive(Validate)]
struct TEIClient {
    #[validate(url)]
    base_url: String,

    channel: OnceCell<Channel>,
}

#[pymethods]
impl TEIClient {
    #[new]
    fn new(base_url: String) -> PyResult<Self> {
        let client = TEIClient {
            base_url,
            channel: OnceCell::new(),
        };
        client.validate().into_pyresult()?;
        Ok(client)
    }
    #[pyo3(text_signature = "(self, query, texts, truncate=false, truncation_direction='Left')")]
    fn arerank<'py>(
        &self,
        python: Python<'py>,
        query: String,
        texts: Vec<String>,
        truncate: bool,
        truncation_direction: Option<String>,
    ) -> PyResult<Bound<'py, PyAny>> {
        let request = RerankRequest {
            query,
            texts,
            truncate,
            truncation_direction: {
                match truncation_direction.unwrap_or("Left".to_string()).as_str() {
                    "Left" => TruncationDirection::Left.into(),
                    "Right" => TruncationDirection::Right.into(),
                    _ => {
                        return Err(PyValueError::new_err(
                            "Invalid truncation_direction value. Must be 'Left' or 'Right'.",
                        ));
                    }
                }
            },
            raw_scores: false,
            return_text: false,
        };
        let base_url = self.base_url.clone();
        let channel_ref = self.channel.clone();
        // Send only non-Python data into the async block
        future_into_py(python, async move {
            let channel = channel_ref
                .get_or_try_init(|| async {
                    let channel = Channel::from_shared(base_url)
                        .into_pyresult()?
                        .connect()
                        .await
                        .into_pyresult()?;
                    Ok::<Channel, PyErr>(channel)
                })
                .await?;
            let mut rerank_client = RerankClient::new(channel.clone());

            let response = rerank_client
                .rerank(request)
                .await
                .into_pyresult()?
                .into_inner();
            let res = response
                .ranks
                .iter()
                .map(|rank| (rank.index, rank.score))
                .collect::<Vec<(u32, f32)>>();
            Ok(res)
        })
    }
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TEIClient>()?;
    Ok(())
}
