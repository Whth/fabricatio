use crate::{Router, parser::JSON_PARSER};
use fabricatio_logger::*;
use futures::StreamExt;
use futures::future::join_all;
use pyo3::exceptions::*;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;
use thryd::{CompletionRequest, RouteGroupName};

#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[derive(Clone)]
#[pyclass(from_py_object)]
struct RouterUsage {
    router: Router,
}

impl RouterUsage {
    pub fn new(router: Router) -> Self {
        Self { router }
    }

    #[allow(clippy::too_many_arguments)]
    pub async fn ask_validate_batch_inner<F, T>(
        &self,
        questions: Vec<String>,
        validator: F,
        default: Option<T>,
        max_validations: usize,

        send_to: RouteGroupName,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
    ) -> PyResult<Vec<Option<T>>>
    where
        F: FnOnce(&str) -> Option<T> + Clone,
        T: Clone,
    {
        if max_validations < 1 {
            return Err(PyValueError::new_err(
                "max_validations must not be smaller than 1",
            ));
        }

        join_all(questions.into_iter().map(|question| {
            self.ask_validate_inner(
                question,
                validator.clone(),
                default.clone(),
                max_validations,
                send_to.clone(),
                stream,
                top_p,
                temperature,
                max_completion_tokens,
                presence_penalty,
                frequency_penalty,
            )
        }))
        .await
        .into_iter()
        .try_collect::<Vec<Option<T>>>()
    }

    #[allow(clippy::too_many_arguments)]
    pub async fn ask_validate_inner<F, T>(
        &self,
        question: String,
        validator: F,
        default: Option<T>,
        max_validations: usize,

        send_to: RouteGroupName,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
    ) -> PyResult<Option<T>>
    where
        F: FnOnce(&str) -> Option<T> + Clone,
    {
        if max_validations < 1 {
            return Err(PyValueError::new_err(
                "max_validations must not be smaller than 1",
            ));
        }

        let req = CompletionRequest {
            message: question,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
        };
        let a: Option<T> = futures::stream::iter(1..=max_validations)
            .map(|i| {
                (
                    i,
                    send_to.clone(),
                    req.clone(),
                    self.router.completion_router.clone(),
                    validator.clone(),
                )
            })
            .map(async move |(i, sd, rq, rtr, vali)| {
                trace!("Validate the {}th time.", i);
                match rtr.invoke(sd, rq).await {
                    Ok(completion) => vali(completion.as_str()),
                    Err(e) => {
                        error!("Error while {}th validation: {}", i, e);
                        None
                    }
                }
            })
            .filter_map(async move |res| res.await)
            .take(1)
            .collect::<Vec<T>>()
            .await
            .pop()
            .or(default);

        Ok(a)
    }

    #[allow(clippy::too_many_arguments)]
    pub async fn mapping_str_inner(
        &self,
        requirement: String,
        k: Option<usize>,
        max_validations: usize,
        default: Option<HashMap<String, String>>,

        send_to: RouteGroupName,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
    ) -> PyResult<Option<HashMap<String, String>>> {
        self.ask_validate_inner(
            requirement,
            |resp| JSON_PARSER.validate_dict_str_str(resp, k, true),
            default,
            max_validations,
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
        )
        .await
    }

    #[allow(clippy::too_many_arguments)]
    pub async fn mapping_str_batch_inner(
        &self,
        requirements: Vec<String>,
        k: Option<usize>,
        max_validations: usize,
        default: Option<HashMap<String, String>>,

        send_to: RouteGroupName,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
    ) -> PyResult<Vec<Option<HashMap<String, String>>>> {
        self.ask_validate_batch_inner(
            requirements,
            |resp| JSON_PARSER.validate_dict_str_str(resp, k, true),
            default,
            max_validations,
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
        )
        .await
    }
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[cfg_attr(not(feature = "stubgen"), remove_gen_stub)]
#[pymethods]
impl RouterUsage {
    #[allow(clippy::too_many_arguments)]
    #[gen_stub(skip)]
    pub fn ask<'a>(
        &self,
        python: Python<'a>,
        question: Bound<'a, PyAny>,
        send_to: RouteGroupName,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
    ) -> PyResult<Bound<'a, PyAny>> {
        if let Ok(msg_seq) = question.extract::<Vec<String>>() {
            self.router.completion_batch(
                python,
                send_to,
                msg_seq,
                stream,
                top_p,
                temperature,
                max_completion_tokens,
                presence_penalty,
                frequency_penalty,
            )
        } else if let Ok(msg) = question.extract::<String>() {
            self.router.completion(
                python,
                send_to,
                msg,
                stream,
                top_p,
                temperature,
                max_completion_tokens,
                presence_penalty,
                frequency_penalty,
            )
        } else {
            Err(PyTypeError::new_err(
                "message must be a string or a list of strings",
            ))
        }
    }

    #[allow(clippy::too_many_arguments)]
    #[gen_stub(skip)]
    pub fn mapping_strings<'a>(
        &self,
        python: Python<'a>,
        requirement: Bound<'a, PyAny>,
        k: Option<usize>,
        max_validations: usize,
        default: Option<HashMap<String, String>>,

        send_to: RouteGroupName,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let slf = self.to_owned();

        if let Ok(msg_seq) = requirement.extract::<Vec<String>>() {
            future_into_py(python, async move {
                slf.mapping_str_batch_inner(
                    msg_seq,
                    k,
                    max_validations,
                    default,
                    send_to,
                    stream,
                    top_p,
                    temperature,
                    max_completion_tokens,
                    presence_penalty,
                    frequency_penalty,
                )
                .await
            })
        } else if let Ok(msg) = requirement.extract::<String>() {
            future_into_py(python, async move {
                slf.mapping_str_inner(
                    msg,
                    k,
                    max_validations,
                    default,
                    send_to,
                    stream,
                    top_p,
                    temperature,
                    max_completion_tokens,
                    presence_penalty,
                    frequency_penalty,
                )
                .await
            })
        } else {
            Err(PyTypeError::new_err(
                "requirement must be a string or a list of strings",
            ))
        }
    }
}

pyo3_stub_gen::inventory::submit! {
    gen_methods_from_python! {
        r#"
        class RouterUsage:
            @overload
            def ask(self, question: str, send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[str]: ...
            @overload
            def ask(self, question: typing.List[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.List[str]]: ...
            @overload
            def mapping_strings(self, requirement: str, k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.Dict[str, str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Optional[typing.Dict[str, str]]]: ...
            @overload
            def mapping_strings(self, requirement: typing.List[str], k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.Dict[str, str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.List[typing.Optional[typing.Dict[str, str]]]]: ...
        "#
    }
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>, router: Router) -> PyResult<()> {
    m.add_class::<RouterUsage>()?;
    m.add("router_usage", RouterUsage::new(router))?;
    Ok(())
}
