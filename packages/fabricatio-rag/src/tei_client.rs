use crate::tei::rerank_client::RerankClient;
use crate::tei::{RerankRequest, TruncationDirection};
use error_mapping::AsPyErr;
use pyo3::exceptions::PyValueError;
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
    #[staticmethod]
    #[gen_stub(override_return_type(type_repr = "typing.Self",imports=("typing",)))]
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
    #[pyo3(text_signature = "(self, query, texts, truncate=false, truncation_direction='Left')")]
    fn arerank<'py>(
        &self,
        python: Python<'py>,
        query: String,
        texts: Vec<String>,
        truncate: bool,
        truncation_direction: String,
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
                .iter()
                .map(|rank| (rank.index, rank.score))
                .collect::<Vec<(u32, f32)>>())
        })
    }
}

/// register the module
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<TEIClient>()?;
    Ok(())
}
