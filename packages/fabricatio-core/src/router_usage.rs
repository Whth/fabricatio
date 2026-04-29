use crate::templates::TEMPLATE_MANAGER;
use crate::{
    Router,
    parser::{CodeSnippet, GENERIC_PARSER, JSON_PARSER, PYTHON_PARSER, SNIPPET_PARSER},
};
use cfg_if::cfg_if;
use error_mapping::AsPyErr;
use fabricatio_config::CONFIG;
use fabricatio_logger::*;
use futures::StreamExt;
use futures::future::join_all;
use pyo3::exceptions::*;
use pyo3::prelude::*;
use pyo3_async_runtimes::tokio::future_into_py;
use pyo3_stub_gen::derive::*;
use serde_json::{Value, json};
use std::collections::HashMap;
use thryd::{CompletionRequest, RouteGroupName};

/// Bundled completion parameters shared across all inner ask/mapping functions.
#[derive(Clone)]
struct CompletionParams {
    send_to: RouteGroupName,
    stream: bool,
    top_p: Option<f32>,
    temperature: Option<f32>,
    max_completion_tokens: Option<u32>,
    presence_penalty: Option<f32>,
    frequency_penalty: Option<f32>,
}

impl CompletionParams {
    fn to_request(&self, message: String) -> CompletionRequest {
        CompletionRequest {
            message,
            stream: self.stream,
            top_p: self.top_p,
            temperature: self.temperature,
            max_completion_tokens: self.max_completion_tokens,
            presence_penalty: self.presence_penalty,
            frequency_penalty: self.frequency_penalty,
        }
    }
}

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

    pub async fn ask_validate_batch_inner<F, T>(
        &self,
        questions: Vec<String>,
        validator: F,
        default: Option<T>,
        max_validations: usize,
        params: &CompletionParams,
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
                params,
            )
        }))
        .await
        .into_iter()
        .try_collect::<Vec<Option<T>>>()
    }

    pub async fn ask_validate_inner<F, T>(
        &self,
        question: String,
        validator: F,
        default: Option<T>,
        max_validations: usize,
        params: &CompletionParams,
    ) -> PyResult<Option<T>>
    where
        F: FnOnce(&str) -> Option<T> + Clone,
    {
        if max_validations < 1 {
            return Err(PyValueError::new_err(
                "max_validations must not be smaller than 1",
            ));
        }

        let req = params.to_request(question);
        let a: Option<T> = futures::stream::iter(1..=max_validations)
            .map(|i| {
                (
                    i,
                    params.send_to.clone(),
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

    pub async fn mapping_str_inner(
        &self,
        requirement: String,
        k: Option<usize>,
        max_validations: usize,
        default: Option<HashMap<String, String>>,
        params: &CompletionParams,
    ) -> PyResult<Option<HashMap<String, String>>> {
        self.ask_validate_inner(
            requirement,
            |resp| JSON_PARSER.validate_dict_str_str(resp, k, true),
            default,
            max_validations,
            params,
        )
        .await
    }

    pub async fn mapping_str_batch_inner(
        &self,
        requirements: Vec<String>,
        k: Option<usize>,
        max_validations: usize,
        default: Option<HashMap<String, String>>,
        params: &CompletionParams,
    ) -> PyResult<Vec<Option<HashMap<String, String>>>> {
        self.ask_validate_batch_inner(
            requirements,
            |resp| JSON_PARSER.validate_dict_str_str(resp, k, true),
            default,
            max_validations,
            params,
        )
        .await
    }
    pub async fn list_str_inner(
        &self,
        requirement: String,
        k: Option<usize>,
        max_validations: usize,
        default: Option<Vec<String>>,
        params: &CompletionParams,
    ) -> PyResult<Option<Vec<String>>> {
        self.ask_validate_inner(
            requirement,
            |resp| JSON_PARSER.validate_list_str(resp, k, true),
            default,
            max_validations,
            params,
        )
        .await
    }

    pub async fn list_str_batch_inner(
        &self,
        requirements: Vec<String>,
        k: Option<usize>,
        max_validations: usize,
        default: Option<Vec<String>>,
        params: &CompletionParams,
    ) -> PyResult<Vec<Option<Vec<String>>>> {
        self.ask_validate_batch_inner(
            requirements,
            |resp| JSON_PARSER.validate_list_str(resp, k, true),
            default,
            max_validations,
            params,
        )
        .await
    }
    pub async fn generic_str_inner(
        &self,
        requirement: String,
        max_validations: usize,
        default: Option<String>,
        params: &CompletionParams,
    ) -> PyResult<Option<String>> {
        self.ask_validate_inner(
            requirement,
            |resp| GENERIC_PARSER.capture(resp),
            default,
            max_validations,
            params,
        )
        .await
    }

    pub async fn generic_str_batch_inner(
        &self,
        requirements: Vec<String>,
        max_validations: usize,
        default: Option<String>,
        params: &CompletionParams,
    ) -> PyResult<Vec<Option<String>>> {
        self.ask_validate_batch_inner(
            requirements,
            |resp| GENERIC_PARSER.capture(resp),
            default,
            max_validations,
            params,
        )
        .await
    }
    pub async fn code_str_inner(
        &self,
        requirement: String,
        max_validations: usize,
        default: Option<String>,
        params: &CompletionParams,
    ) -> PyResult<Option<String>> {
        self.ask_validate_inner(
            requirement,
            |resp| PYTHON_PARSER.capture(resp),
            default,
            max_validations,
            params,
        )
        .await
    }

    pub async fn code_str_batch_inner(
        &self,
        requirements: Vec<String>,
        max_validations: usize,
        default: Option<String>,
        params: &CompletionParams,
    ) -> PyResult<Vec<Option<String>>> {
        self.ask_validate_batch_inner(
            requirements,
            |resp| PYTHON_PARSER.capture(resp),
            default,
            max_validations,
            params,
        )
        .await
    }
    pub async fn code_snippets_inner(
        &self,
        requirement: String,
        max_validations: usize,
        default: Option<Vec<CodeSnippet>>,
        params: &CompletionParams,
    ) -> PyResult<Option<Vec<CodeSnippet>>> {
        self.ask_validate_inner(
            requirement,
            |resp| {
                let v = SNIPPET_PARSER.parse(resp);
                if v.is_empty() { None } else { Some(v) }
            },
            default,
            max_validations,
            params,
        )
        .await
    }

    pub async fn code_snippets_batch_inner(
        &self,
        requirements: Vec<String>,
        max_validations: usize,
        default: Option<Vec<CodeSnippet>>,
        params: &CompletionParams,
    ) -> PyResult<Vec<Option<Vec<CodeSnippet>>>> {
        self.ask_validate_batch_inner(
            requirements,
            |resp| {
                let v = SNIPPET_PARSER.parse(resp);
                if v.is_empty() { None } else { Some(v) }
            },
            default,
            max_validations,
            params,
        )
        .await
    }
    pub async fn judge_inner(
        &self,
        requirement: String,
        max_validations: usize,
        default: Option<bool>,
        params: &CompletionParams,
    ) -> PyResult<Option<bool>> {
        self.ask_validate_inner(
            requirement,
            |resp| {
                JSON_PARSER
                    .capture(resp, true)
                    .and_then(|s| serde_json::from_str::<bool>(&s).ok())
            },
            default,
            max_validations,
            params,
        )
        .await
    }

    pub async fn judge_batch_inner(
        &self,
        requirements: Vec<String>,
        max_validations: usize,
        default: Option<bool>,
        params: &CompletionParams,
    ) -> PyResult<Vec<Option<bool>>> {
        self.ask_validate_batch_inner(
            requirements,
            |resp| {
                JSON_PARSER
                    .capture(resp, true)
                    .and_then(|s| serde_json::from_str::<bool>(&s).ok())
            },
            default,
            max_validations,
            params,
        )
        .await
    }
    pub async fn choose_inner(
        &self,
        requirement: String,
        valid_names: Vec<String>,
        k: Option<usize>,
        max_validations: usize,
        default: Option<Vec<usize>>,
        params: &CompletionParams,
    ) -> PyResult<Option<Vec<usize>>> {
        self.ask_validate_inner(
            requirement,
            |resp| {
                let names = JSON_PARSER.validate_list_str(resp, k, true)?;
                let indices: Vec<usize> = names
                    .iter()
                    .filter_map(|n| valid_names.iter().position(|v| v == n))
                    .collect();
                if names.is_empty() || !indices.is_empty() {
                    Some(indices)
                } else {
                    None
                }
            },
            default,
            max_validations,
            params,
        )
        .await
    }

    pub async fn choose_batch_inner(
        &self,
        requirements: Vec<String>,
        valid_names: Vec<String>,
        k: Option<usize>,
        max_validations: usize,
        default: Option<Vec<usize>>,
        params: &CompletionParams,
    ) -> PyResult<Vec<Option<Vec<usize>>>> {
        self.ask_validate_batch_inner(
            requirements,
            |resp| {
                let names = JSON_PARSER.validate_list_str(resp, k, true)?;
                let indices: Vec<usize> = names
                    .iter()
                    .filter_map(|n| valid_names.iter().position(|v| v == n))
                    .collect();
                if names.is_empty() || !indices.is_empty() {
                    Some(indices)
                } else {
                    None
                }
            },
            default,
            max_validations,
            params,
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
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
        };
        if let Ok(msg_seq) = question.extract::<Vec<String>>() {
            self.router.completion_batch(
                python,
                params.send_to.clone(),
                msg_seq,
                params.stream,
                params.top_p,
                params.temperature,
                params.max_completion_tokens,
                params.presence_penalty,
                params.frequency_penalty,
            )
        } else if let Ok(msg) = question.extract::<String>() {
            self.router.completion(
                python,
                params.send_to.clone(),
                msg,
                params.stream,
                params.top_p,
                params.temperature,
                params.max_completion_tokens,
                params.presence_penalty,
                params.frequency_penalty,
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
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
        };

        if let Ok(reqs) = requirement.extract::<Vec<String>>() {
            future_into_py(python, async move {
                let data: Vec<Value> = reqs
                    .iter()
                    .map(|r| json!({"requirement": r, "k": k}))
                    .collect();
                let rendered = TEMPLATE_MANAGER
                    .render_batch(&CONFIG.templates.mapping_template, &data)
                    .into_pyresult()?;
                slf.mapping_str_batch_inner(rendered, k, max_validations, default, &params)
                    .await
            })
        } else if let Ok(req) = requirement.extract::<String>() {
            future_into_py(python, async move {
                let data = json!({"requirement": req, "k": k});
                let rendered = TEMPLATE_MANAGER
                    .render(&CONFIG.templates.mapping_template, &data)
                    .into_pyresult()?;
                slf.mapping_str_inner(rendered, k, max_validations, default, &params)
                    .await
            })
        } else {
            Err(PyTypeError::new_err(
                "requirement must be a string or a list of strings",
            ))
        }
    }
    #[allow(clippy::too_many_arguments)]
    #[gen_stub(skip)]
    pub fn listing_strings<'a>(
        &self,
        python: Python<'a>,
        requirement: Bound<'a, PyAny>,
        k: Option<usize>,
        max_validations: usize,
        default: Option<Vec<String>>,

        send_to: RouteGroupName,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let slf = self.to_owned();
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
        };

        if let Ok(reqs) = requirement.extract::<Vec<String>>() {
            future_into_py(python, async move {
                let data: Vec<Value> = reqs
                    .iter()
                    .map(|r| json!({"requirement": r, "k": k}))
                    .collect();
                let rendered = TEMPLATE_MANAGER
                    .render_batch(&CONFIG.templates.liststr_template, &data)
                    .into_pyresult()?;

                slf.list_str_batch_inner(rendered, k, max_validations, default, &params)
                    .await
            })
        } else if let Ok(req) = requirement.extract::<String>() {
            future_into_py(python, async move {
                let data = json!({"requirement": req, "k": k});
                let rendered = TEMPLATE_MANAGER
                    .render(&CONFIG.templates.liststr_template, &data)
                    .into_pyresult()?;

                slf.list_str_inner(rendered, k, max_validations, default, &params)
                    .await
            })
        } else {
            Err(PyTypeError::new_err(
                "requirement must be a string or a list of strings",
            ))
        }
    }
    #[allow(clippy::too_many_arguments)]
    #[gen_stub(skip)]
    pub fn generic_string<'a>(
        &self,
        python: Python<'a>,
        requirement: Bound<'a, PyAny>,
        max_validations: usize,
        default: Option<String>,

        send_to: RouteGroupName,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let slf = self.to_owned();
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
        };

        if let Ok(reqs) = requirement.extract::<Vec<String>>() {
            future_into_py(python, async move {
                let data: Vec<Value> = reqs
                    .iter()
                    .map(|r| json!({"requirement": r, "language": "String"}))
                    .collect();
                let rendered = TEMPLATE_MANAGER
                    .render_batch(&CONFIG.templates.generic_string_template, &data)
                    .into_pyresult()?;

                slf.generic_str_batch_inner(rendered, max_validations, default, &params)
                    .await
            })
        } else if let Ok(req) = requirement.extract::<String>() {
            future_into_py(python, async move {
                let data = json!({"requirement": req, "language": "String"});
                let rendered = TEMPLATE_MANAGER
                    .render(&CONFIG.templates.generic_string_template, &data)
                    .into_pyresult()?;

                slf.generic_str_inner(rendered, max_validations, default, &params)
                    .await
            })
        } else {
            Err(PyTypeError::new_err(
                "requirement must be a string or a list of strings",
            ))
        }
    }
    #[allow(clippy::too_many_arguments)]
    #[gen_stub(skip)]
    pub fn code_string<'a>(
        &self,
        python: Python<'a>,
        requirement: Bound<'a, PyAny>,
        code_language: Option<String>,
        max_validations: usize,
        default: Option<String>,

        send_to: RouteGroupName,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let slf = self.to_owned();
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
        };

        if let Ok(reqs) = requirement.extract::<Vec<String>>() {
            future_into_py(python, async move {
                let data: Vec<Value> = reqs
                    .iter()
                    .map(|r| json!({"requirement": r, "code_language": code_language}))
                    .collect();
                let rendered = TEMPLATE_MANAGER
                    .render_batch(&CONFIG.templates.code_string_template, &data)
                    .into_pyresult()?;

                slf.code_str_batch_inner(rendered, max_validations, default, &params)
                    .await
            })
        } else if let Ok(req) = requirement.extract::<String>() {
            future_into_py(python, async move {
                let data = json!({"requirement": req, "code_language": code_language});
                let rendered = TEMPLATE_MANAGER
                    .render(&CONFIG.templates.code_string_template, &data)
                    .into_pyresult()?;

                slf.code_str_inner(rendered, max_validations, default, &params)
                    .await
            })
        } else {
            Err(PyTypeError::new_err(
                "requirement must be a string or a list of strings",
            ))
        }
    }
    #[allow(clippy::too_many_arguments)]
    #[gen_stub(skip)]
    pub fn code_snippets<'a>(
        &self,
        python: Python<'a>,
        requirement: Bound<'a, PyAny>,
        code_language: Option<String>,
        max_validations: usize,
        default: Option<Vec<CodeSnippet>>,

        send_to: RouteGroupName,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let slf = self.to_owned();
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
        };

        if let Ok(reqs) = requirement.extract::<Vec<String>>() {
            future_into_py(python, async move {
                let data: Vec<Value> = reqs
                    .iter()
                    .map(|r| json!({"requirement": r, "code_language": code_language}))
                    .collect();
                let rendered = TEMPLATE_MANAGER
                    .render_batch(&CONFIG.templates.code_snippet_template, &data)
                    .into_pyresult()?;

                slf.code_snippets_batch_inner(rendered, max_validations, default, &params)
                    .await
            })
        } else if let Ok(req) = requirement.extract::<String>() {
            future_into_py(python, async move {
                let data = json!({"requirement": req, "code_language": code_language});
                let rendered = TEMPLATE_MANAGER
                    .render(&CONFIG.templates.code_snippet_template, &data)
                    .into_pyresult()?;

                slf.code_snippets_inner(rendered, max_validations, default, &params)
                    .await
            })
        } else {
            Err(PyTypeError::new_err(
                "requirement must be a string or a list of strings",
            ))
        }
    }
    #[allow(clippy::too_many_arguments)]
    #[gen_stub(skip)]
    pub fn judging<'a>(
        &self,
        python: Python<'a>,
        requirement: Bound<'a, PyAny>,
        max_validations: usize,
        default: Option<bool>,
        affirm_case: String,
        deny_case: String,

        send_to: RouteGroupName,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let slf = self.to_owned();
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
        };

        if let Ok(reqs) = requirement.extract::<Vec<String>>() {
            future_into_py(python, async move {
                let data: Vec<Value> = reqs.iter().map(|r| json!({"prompt": r, "affirm_case": affirm_case.clone(), "deny_case": deny_case.clone()})).collect();
                let rendered = TEMPLATE_MANAGER
                    .render_batch(&CONFIG.templates.make_judgment_template, &data)
                    .into_pyresult()?;

                slf.judge_batch_inner(rendered, max_validations, default, &params)
                    .await
            })
        } else if let Ok(req) = requirement.extract::<String>() {
            future_into_py(python, async move {
                let data =
                    json!({"prompt": req, "affirm_case": affirm_case, "deny_case": deny_case});
                let rendered = TEMPLATE_MANAGER
                    .render(&CONFIG.templates.make_judgment_template, &data)
                    .into_pyresult()?;

                slf.judge_inner(rendered, max_validations, default, &params)
                    .await
            })
        } else {
            Err(PyTypeError::new_err(
                "requirement must be a string or a list of strings",
            ))
        }
    }
    #[allow(clippy::too_many_arguments)]
    #[gen_stub(skip)]
    pub fn choosing<'a>(
        &self,
        python: Python<'a>,
        requirement: Bound<'a, PyAny>,
        valid_names: Vec<String>,
        k: Option<usize>,
        max_validations: usize,
        default: Option<Vec<usize>>,

        send_to: RouteGroupName,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
    ) -> PyResult<Bound<'a, PyAny>> {
        let slf = self.to_owned();
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
        };

        if let Ok(reqs) = requirement.extract::<Vec<String>>() {
            future_into_py(python, async move {
                slf.choose_batch_inner(reqs, valid_names, k, max_validations, default, &params)
                    .await
            })
        } else if let Ok(req) = requirement.extract::<String>() {
            future_into_py(python, async move {
                slf.choose_inner(req, valid_names, k, max_validations, default, &params)
                    .await
            })
        } else {
            Err(PyTypeError::new_err(
                "requirement must be a string or a list of strings",
            ))
        }
    }
}
#[cfg(feature = "stubgen")]
pyo3_stub_gen::inventory::submit! {
    gen_methods_from_python! {
        r#"
        class RouterUsage:
            @overload
            def ask(self, question: str, send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[str]: ...
            @overload
            def ask(self, question: typing.List[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.List[str]]: ...
            @overload
            def ask(self, question: typing.Union[str, typing.List[str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Union[str, typing.List[str]]]: ...
            @overload
            def mapping_strings(self, requirement: str, k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.Dict[str, str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Optional[typing.Dict[str, str]]]: ...
            @overload
            def mapping_strings(self, requirement: typing.List[str], k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.Dict[str, str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.List[typing.Optional[typing.Dict[str, str]]]]: ...
            @overload
            def mapping_strings(self, requirement: typing.Union[str, typing.List[str]], k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.Dict[str, str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Union[typing.Optional[typing.Dict[str, str]], typing.List[typing.Optional[typing.Dict[str, str]]]]]: ...
            @overload
            def listing_strings(self, requirement: str, k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.List[str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Optional[typing.List[str]]]: ...
            @overload
            def listing_strings(self, requirement: typing.List[str], k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.List[str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.List[typing.Optional[typing.List[str]]]]: ...
            @overload
            def listing_strings(self, requirement: typing.Union[str, typing.List[str]], k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.List[str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Union[typing.Optional[typing.List[str]], typing.List[typing.Optional[typing.List[str]]]]]: ...
            @overload
            def generic_string(self, requirement: str, max_validations: int, default: typing.Optional[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Optional[str]]: ...
            @overload
            def generic_string(self, requirement: typing.List[str], max_validations: int, default: typing.Optional[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.List[typing.Optional[str]]]: ...
            @overload
            def generic_string(self, requirement: typing.Union[str, typing.List[str]], max_validations: int, default: typing.Optional[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Union[typing.Optional[str], typing.List[typing.Optional[str]]]]: ...
            @overload
            def code_string(self, requirement: str, code_language: typing.Optional[str], max_validations: int, default: typing.Optional[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Optional[str]]: ...
            @overload
            def code_string(self, requirement: typing.List[str], code_language: typing.Optional[str], max_validations: int, default: typing.Optional[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.List[typing.Optional[str]]]: ...
            @overload
            def code_string(self, requirement: typing.Union[str, typing.List[str]], code_language: typing.Optional[str], max_validations: int, default: typing.Optional[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Union[typing.Optional[str], typing.List[typing.Optional[str]]]]: ...
            @overload
            def code_snippets(self, requirement: str, code_language: typing.Optional[str], max_validations: int, default: typing.Optional[typing.List[CodeSnippet]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Optional[typing.List[CodeSnippet]]]: ...
            @overload
            def code_snippets(self, requirement: typing.List[str], code_language: typing.Optional[str], max_validations: int, default: typing.Optional[typing.List[CodeSnippet]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.List[typing.Optional[typing.List[CodeSnippet]]]]: ...
            @overload
            def code_snippets(self, requirement: typing.Union[str, typing.List[str]], code_language: typing.Optional[str], max_validations: int, default: typing.Optional[typing.List[CodeSnippet]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Union[typing.Optional[typing.List[CodeSnippet]], typing.List[typing.Optional[typing.List[CodeSnippet]]]]]: ...
            @overload
            def judging(self, requirement: str, max_validations: int, default: typing.Optional[bool], affirm_case: str, deny_case: str, send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Optional[bool]]: ...
            @overload
            def judging(self, requirement: typing.List[str], max_validations: int, default: typing.Optional[bool], affirm_case: str, deny_case: str, send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.List[typing.Optional[bool]]]: ...
            @overload
            def judging(self, requirement: typing.Union[str, typing.List[str]], max_validations: int, default: typing.Optional[bool], affirm_case: str, deny_case: str, send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Union[typing.Optional[bool], typing.List[typing.Optional[bool]]]]: ...
            @overload
            def choosing(self, requirement: str, valid_names: typing.List[str], k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.List[int]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Optional[typing.List[int]]]: ...
            @overload
            def choosing(self, requirement: typing.List[str], valid_names: typing.List[str], k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.List[int]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.List[typing.Optional[typing.List[int]]]]: ...
            @overload
            def choosing(self, requirement: typing.Union[str, typing.List[str]], valid_names: typing.List[str], k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.List[int]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float]) -> typing.Awaitable[typing.Union[typing.Optional[typing.List[int]], typing.List[typing.Optional[typing.List[int]]]]]: ...
        "#
    }
}
cfg_if!(
    if #[cfg(feature = "stubgen")]    {
        use pyo3_stub_gen::module_variable;
        module_variable!("fabricatio_core.rust", ROUTER_USAGE_VARNAME, RouterUsage);
    }
);

const ROUTER_USAGE_VARNAME: &str = "router_usage";

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>, router: Router) -> PyResult<()> {
    m.add_class::<RouterUsage>()?;
    m.add(ROUTER_USAGE_VARNAME, RouterUsage::new(router))?;
    Ok(())
}
