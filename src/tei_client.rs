use crate::tei::rerank_client::RerankClient;
use crate::tei::{RerankRequest, TruncationDirection};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use validator::Validate;

#[pyclass]
#[derive(Validate)]
struct TEIClient {
    #[validate(url)]
    base_url: String,
}

#[pymethods]
impl TEIClient {
    #[new]
    fn new(base_url: String) -> Self {
        TEIClient { base_url }
    }
    #[pyo3(text_signature = "(self, query, texts, truncate=false, truncation_direction='Left')")]
    fn arerank<'py>(
        &mut self,
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
                    "Left" => i32::from(TruncationDirection::Left),
                    "Right" => i32::from(TruncationDirection::Right),
                    _ => {
                        return Err(PyErr::new::<PyRuntimeError, _>(
                            "Invalid truncation_direction value. Must be 'Left' or 'Right'."
                                .to_string(),
                        ));
                    }
                }
            },
            raw_scores: false,
            return_text: false,
        };

        let base_url = self.base_url.clone();

        // Send only non-Python data into the async block
        future_into_py(python, async move {
            let mut rerank_client = RerankClient::connect(base_url)
                .await
                .map_err(|e| PyErr::new::<PyRuntimeError, _>(e.to_string()))?;

            let response = rerank_client
                .rerank(request)
                .await
                .map_err(|e| PyErr::new::<PyRuntimeError, _>(e.to_string()))?
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
