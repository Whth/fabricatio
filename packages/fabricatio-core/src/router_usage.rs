use crate::parser::{
    CodeSnippet, GENERIC_PARSER, JSON_PARSER, PYTHON_PARSER, SNIPPET_PARSER, ValidatedDict,
    ValueType,
};
use crate::templates::TEMPLATE_MANAGER;
use cfg_if::cfg_if;
use error_mapping::AsPyErr;
use fabricatio_config::CONFIG;
use fabricatio_logger::*;
use fabricatio_router::Router;
use fabricatio_router::{CompletionRequest, RouteGroupName};
use futures::StreamExt;
use futures::future::join_all;
use pyo3::exceptions::*;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyType};
use pyo3::{BoundObject, IntoPyObjectExt};
use pyo3_async_runtimes::tokio::future_into_py;
use pyo3_stub_gen::derive::*;
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
use std::collections::HashMap;
use std::hash::Hash;
use std::sync::Arc;

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
    no_cache: bool,
}

#[derive(Clone)]
enum Batch<V> {
    Single(V),
    Batch(Vec<V>),
}

impl<V> Batch<V> {
    fn map<U>(self, mut f: impl FnMut(V) -> U) -> Batch<U> {
        match self {
            Batch::Single(v) => Batch::Single(f(v)),
            Batch::Batch(v) => Batch::Batch(v.into_iter().map(|v| f(v)).collect()),
        }
    }
}

impl Batch<Value> {
    fn render_template(self, template: &str) -> PyResult<Batch<String>> {
        match self {
            Batch::Single(data) => Ok(Batch::Single(
                TEMPLATE_MANAGER.render(template, &data).into_pyresult()?,
            )),
            Batch::Batch(data) => Ok(Batch::Batch(
                TEMPLATE_MANAGER
                    .render_batch(template, &data)
                    .into_pyresult()?,
            )),
        }
    }
}

fn extract_batch(ob: &Bound<'_, PyAny>) -> PyResult<Batch<String>> {
    if let Ok(v) = ob.extract::<Vec<String>>() {
        Ok(Batch::Batch(v))
    } else if let Ok(s) = ob.extract::<String>() {
        Ok(Batch::Single(s))
    } else {
        Err(PyTypeError::new_err(
            "requirement must be a string or a list of strings",
        ))
    }
}

fn batch_to_py<'py, T: IntoPyObject<'py>>(
    batch: Batch<Option<T>>,
    py: Python<'py>,
) -> PyResult<Py<PyAny>>
where
    PyErr: From<T::Error>,
{
    Ok(match batch {
        Batch::Single(Some(v)) => v.into_pyobject(py)?.unbind().into_any(),
        Batch::Single(None) => py.None(),
        Batch::Batch(v) => v.into_pyobject(py)?.unbind().into_any(),
    })
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
                match rtr.invoke(sd, rq, params.no_cache).await {
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

    pub async fn ask_validate<F, T>(
        &self,
        question: Batch<String>,
        validator: F,
        default: Option<T>,
        max_validations: usize,
        params: &CompletionParams,
    ) -> PyResult<Batch<Option<T>>>
    where
        F: FnOnce(&str) -> Option<T> + Clone,
        T: Clone,
    {
        match question {
            Batch::Single(s) => self
                .ask_validate_inner(s, validator, default, max_validations, params)
                .await
                .map(Batch::Single),
            Batch::Batch(s_seq) => self
                .ask_validate_batch_inner(s_seq, validator, default, max_validations, params)
                .await
                .map(Batch::Batch),
        }
    }

    pub async fn mapping_kv_rs<
        K: DeserializeOwned + Eq + Hash + Clone,
        V: DeserializeOwned + Clone,
    >(
        &self,
        requirement: Batch<String>,
        k: Option<usize>,
        max_validations: usize,
        default: Option<HashMap<K, V>>,
        params: &CompletionParams,
    ) -> PyResult<Batch<Option<HashMap<K, V>>>> {
        self.ask_validate(
            requirement,
            |resp| JSON_PARSER.validate_dict_inner::<K, V>(resp, k, true),
            default,
            max_validations,
            params,
        )
        .await
    }
    #[allow(clippy::too_many_arguments)]
    pub async fn mapping_kv_inner(
        &self,
        requirement: Batch<String>,
        key_type: ValueType,
        value_type: ValueType,
        k: Option<usize>,
        max_validations: usize,
        default: Option<ValidatedDict>,
        params: &CompletionParams,
    ) -> PyResult<Batch<Option<ValidatedDict>>> {
        self.ask_validate(
            requirement,
            |resp| JSON_PARSER.validate_dict_kv_inner(resp, key_type, value_type, k, true),
            default,
            max_validations,
            params,
        )
        .await
    }

    pub async fn list_str_inner(
        &self,
        requirement: Batch<String>,
        k: Option<usize>,
        max_validations: usize,
        default: Option<Vec<String>>,
        params: &CompletionParams,
    ) -> PyResult<Batch<Option<Vec<String>>>> {
        self.ask_validate(
            requirement,
            |resp| JSON_PARSER.validate_list_inner(resp, k, true),
            default,
            max_validations,
            params,
        )
        .await
    }

    pub async fn generic_str_inner(
        &self,
        requirement: Batch<String>,
        max_validations: usize,
        default: Option<String>,
        params: &CompletionParams,
    ) -> PyResult<Batch<Option<String>>> {
        self.ask_validate(
            requirement,
            |resp| GENERIC_PARSER.capture(resp),
            default,
            max_validations,
            params,
        )
        .await
    }

    pub async fn code_str_inner(
        &self,
        requirement: Batch<String>,

        max_validations: usize,
        default: Option<String>,
        params: &CompletionParams,
    ) -> PyResult<Batch<Option<String>>> {
        self.ask_validate(
            requirement,
            |resp| PYTHON_PARSER.capture(resp),
            default,
            max_validations,
            params,
        )
        .await
    }

    pub async fn code_snippets_inner(
        &self,
        requirement: Batch<String>,
        max_validations: usize,
        default: Option<Vec<CodeSnippet>>,
        params: &CompletionParams,
    ) -> PyResult<Batch<Option<Vec<CodeSnippet>>>> {
        self.ask_validate(
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

    pub async fn judge_inner(
        &self,
        requirement: Batch<String>,
        max_validations: usize,
        default: Option<bool>,
        params: &CompletionParams,
    ) -> PyResult<Batch<Option<bool>>> {
        self.ask_validate(
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

    fn choose_validate(resp: &str, valid_names: &[String], k: Option<usize>) -> Option<Vec<usize>> {
        let names = JSON_PARSER.validate_list_inner::<String>(resp, k, true)?;
        let indices: Vec<usize> = names
            .iter()
            .filter_map(|n| valid_names.iter().position(|v| v == n))
            .collect();
        if names.is_empty() || !indices.is_empty() {
            Some(indices)
        } else {
            None
        }
    }

    pub async fn choose_inner(
        &self,
        requirement: Batch<String>,
        valid_names: Vec<String>,
        k: Option<usize>,
        max_validations: usize,
        default: Option<Vec<usize>>,
        params: &CompletionParams,
    ) -> PyResult<Batch<Option<Vec<usize>>>> {
        self.ask_validate(
            requirement,
            |resp| Self::choose_validate(resp, &valid_names, k),
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
        no_cache: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
            no_cache,
        };
        let question = extract_batch(&question)?;
        match question {
            Batch::Single(msg) => self.router.completion(
                python,
                params.send_to.clone(),
                msg,
                params.stream,
                params.top_p,
                params.temperature,
                params.max_completion_tokens,
                params.presence_penalty,
                params.frequency_penalty,
                params.no_cache,
            ),
            Batch::Batch(msg_seq) => self.router.completion_batch(
                python,
                params.send_to.clone(),
                msg_seq,
                params.stream,
                params.top_p,
                params.temperature,
                params.max_completion_tokens,
                params.presence_penalty,
                params.frequency_penalty,
                params.no_cache,
            ),
        }
    }

    /// Asynchronously maps a requirement to a key-value dictionary via LLM, with typed key/value validation.
    ///
    /// Unlike `mapping_strings` (str→str only), this method supports arbitrary key and value types
    /// controlled by `key_type` and `value_type` parameters.
    ///
    /// # Arguments
    /// * `requirement` - A single string or list of strings describing the mapping task.
    /// * `key_type` - Expected type for dictionary keys (e.g. `ValueType::String`, `ValueType::Int`).
    /// * `value_type` - Expected type for dictionary values.
    /// * `k` - Optional number of key-value pairs to generate.
    /// * `max_validations` - Maximum number of LLM retry attempts for validation.
    /// * `default` - Optional fallback dictionary returned when all attempts fail.
    ///
    /// Returns `Optional[Dict]` for single requirement, `List[Optional[Dict]]` for batch.
    #[allow(clippy::too_many_arguments)]
    #[gen_stub(skip)]
    pub fn mapping_kv<'a>(
        &self,
        python: Python<'a>,
        requirement: Bound<'a, PyAny>,
        key_type: Bound<'a, PyType>,
        value_type: Bound<'a, PyType>,
        k: Option<usize>,
        max_validations: usize,
        default: Option<Bound<'a, PyDict>>,
        send_to: RouteGroupName,
        stream: bool,
        top_p: Option<f32>,
        temperature: Option<f32>,
        max_completion_tokens: Option<u32>,
        presence_penalty: Option<f32>,
        frequency_penalty: Option<f32>,
        no_cache: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let requirement = extract_batch(&requirement)?;
        let slf = self.to_owned();
        let default = default.map(|d| d.unbind());
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
            no_cache,
        };

        let key_type = ValueType::from_type(key_type)?;
        let value_type = ValueType::from_type(value_type)?;
        future_into_py(python, async move {
            let rendered = requirement
                .map(|r| json!({"requirement": r, "k": k}))
                .render_template(&CONFIG.templates.mapping_template)?;
            let result = slf
                .mapping_kv_inner(
                    rendered,
                    key_type,
                    value_type,
                    k,
                    max_validations,
                    None,
                    &params,
                )
                .await?;
            Python::try_attach(|py| {
                let mapped = result.map(|vd| match vd {
                    Some(d) => Some(d.into_py_any(py)),
                    None => default.as_ref().map(|d| d.bind(py).clone().into_any()),
                });
                batch_to_py(mapped, py)
            })
            .expect("Python not initialized")
        })
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
        no_cache: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let requirement = extract_batch(&requirement)?;
        let slf = self.to_owned();
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
            no_cache,
        };
        future_into_py(python, async move {
            let rendered = requirement
                .map(|r| json!({"requirement": r, "k": k}))
                .render_template(&CONFIG.templates.liststr_template)?;
            let result = slf
                .list_str_inner(rendered, k, max_validations, default, &params)
                .await?;
            Python::try_attach(|py| batch_to_py(result, py)).expect("Python not initialized")
        })
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
        no_cache: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let requirement = extract_batch(&requirement)?;
        let slf = self.to_owned();
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
            no_cache,
        };
        future_into_py(python, async move {
            let rendered = requirement
                .map(|r| json!({"requirement": r, "language": "String"}))
                .render_template(&CONFIG.templates.generic_string_template)?;
            let result = slf
                .generic_str_inner(rendered, max_validations, default, &params)
                .await?;
            Python::try_attach(|py| batch_to_py(result, py)).expect("Python not initialized")
        })
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
        no_cache: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let requirement = extract_batch(&requirement)?;
        let slf = self.to_owned();
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
            no_cache,
        };
        future_into_py(python, async move {
            let rendered = requirement
                .map(|r| json!({"requirement": r, "code_language": code_language}))
                .render_template(&CONFIG.templates.code_string_template)?;
            let result = slf
                .code_str_inner(rendered, max_validations, default, &params)
                .await?;
            Python::try_attach(|py| batch_to_py(result, py)).expect("Python not initialized")
        })
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
        no_cache: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let requirement = extract_batch(&requirement)?;
        let slf = self.to_owned();
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
            no_cache,
        };
        future_into_py(python, async move {
            let rendered = requirement
                .map(|r| json!({"requirement": r, "code_language": code_language}))
                .render_template(&CONFIG.templates.code_snippet_template)?;
            let result = slf
                .code_snippets_inner(rendered, max_validations, default, &params)
                .await?;
            Python::try_attach(|py| batch_to_py(result, py)).expect("Python not initialized")
        })
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
        no_cache: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let requirement = extract_batch(&requirement)?;
        let slf = self.to_owned();
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
            no_cache,
        };
        future_into_py(python, async move {
            let rendered = requirement
                .map(|r| {
                    json!({"prompt": r, "affirm_case": affirm_case.clone(), "deny_case": deny_case.clone()})
                })
                .render_template(&CONFIG.templates.make_judgment_template)?;
            let result = slf
                .judge_inner(rendered, max_validations, default, &params)
                .await?;
            Python::try_attach(|py| batch_to_py(result, py)).expect("Python not initialized")
        })
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
        no_cache: bool,
    ) -> PyResult<Bound<'a, PyAny>> {
        let requirement = extract_batch(&requirement)?;
        let slf = self.to_owned();
        let params = CompletionParams {
            send_to,
            stream,
            top_p,
            temperature,
            max_completion_tokens,
            presence_penalty,
            frequency_penalty,
            no_cache,
        };
        future_into_py(python, async move {
            let result = slf
                .choose_inner(
                    requirement,
                    valid_names,
                    k,
                    max_validations,
                    default,
                    &params,
                )
                .await?;
            Python::try_attach(|py| batch_to_py(result, py)).expect("Python not initialized")
        })
    }
}
#[cfg(feature = "stubgen")]
pyo3_stub_gen::inventory::submit! {
    gen_methods_from_python! {
        r#"
        class RouterUsage:
            @overload
            def ask(self, question: str, send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[str]: ...
            @overload
            def ask(self, question: typing.List[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.List[str]]: ...
            @overload
            def ask(self, question: typing.Union[str, typing.List[str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Union[str, typing.List[str]]]: ...
            @overload
            def mapping_kv(self, requirement: str, key_type: ValueType, value_type: ValueType, k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.Dict[str, str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Optional[typing.Dict[str, str]]]: ...
            @overload
            def mapping_kv(self, requirement: typing.List[str], key_type: ValueType, value_type: ValueType, k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.Dict[str, str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.List[typing.Optional[typing.Dict[str, str]]]]: ...
            @overload
            def mapping_kv(self, requirement: typing.Union[str, typing.List[str]], key_type: ValueType, value_type: ValueType, k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.Dict[str, str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Union[typing.Optional[typing.Dict[str, str]], typing.List[typing.Optional[typing.Dict[str, str]]]]]: ...
            @overload
            def listing_strings(self, requirement: str, k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.List[str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Optional[typing.List[str]]]: ...
            @overload
            def listing_strings(self, requirement: typing.List[str], k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.List[str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.List[typing.Optional[typing.List[str]]]]: ...
            @overload
            def listing_strings(self, requirement: typing.Union[str, typing.List[str]], k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.List[str]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Union[typing.Optional[typing.List[str]], typing.List[typing.Optional[typing.List[str]]]]]: ...
            @overload
            def generic_string(self, requirement: str, max_validations: int, default: typing.Optional[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Optional[str]]: ...
            @overload
            def generic_string(self, requirement: typing.List[str], max_validations: int, default: typing.Optional[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.List[typing.Optional[str]]]: ...
            @overload
            def generic_string(self, requirement: typing.Union[str, typing.List[str]], max_validations: int, default: typing.Optional[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Union[typing.Optional[str], typing.List[typing.Optional[str]]]]: ...
            @overload
            def code_string(self, requirement: str, code_language: typing.Optional[str], max_validations: int, default: typing.Optional[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Optional[str]]: ...
            @overload
            def code_string(self, requirement: typing.List[str], code_language: typing.Optional[str], max_validations: int, default: typing.Optional[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.List[typing.Optional[str]]]: ...
            @overload
            def code_string(self, requirement: typing.Union[str, typing.List[str]], code_language: typing.Optional[str], max_validations: int, default: typing.Optional[str], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Union[typing.Optional[str], typing.List[typing.Optional[str]]]]: ...
            @overload
            def code_snippets(self, requirement: str, code_language: typing.Optional[str], max_validations: int, default: typing.Optional[typing.List[CodeSnippet]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Optional[typing.List[CodeSnippet]]]: ...
            @overload
            def code_snippets(self, requirement: typing.List[str], code_language: typing.Optional[str], max_validations: int, default: typing.Optional[typing.List[CodeSnippet]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.List[typing.Optional[typing.List[CodeSnippet]]]]: ...
            @overload
            def code_snippets(self, requirement: typing.Union[str, typing.List[str]], code_language: typing.Optional[str], max_validations: int, default: typing.Optional[typing.List[CodeSnippet]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Union[typing.Optional[typing.List[CodeSnippet]], typing.List[typing.Optional[typing.List[CodeSnippet]]]]]: ...
            @overload
            def judging(self, requirement: str, max_validations: int, default: typing.Optional[bool], affirm_case: str, deny_case: str, send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Optional[bool]]: ...
            @overload
            def judging(self, requirement: typing.List[str], max_validations: int, default: typing.Optional[bool], affirm_case: str, deny_case: str, send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.List[typing.Optional[bool]]]: ...
            @overload
            def judging(self, requirement: typing.Union[str, typing.List[str]], max_validations: int, default: typing.Optional[bool], affirm_case: str, deny_case: str, send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Union[typing.Optional[bool], typing.List[typing.Optional[bool]]]]: ...
            @overload
            def choosing(self, requirement: str, valid_names: typing.List[str], k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.List[int]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Optional[typing.List[int]]]: ...
            @overload
            def choosing(self, requirement: typing.List[str], valid_names: typing.List[str], k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.List[int]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.List[typing.Optional[typing.List[int]]]]: ...
            @overload
            def choosing(self, requirement: typing.Union[str, typing.List[str]], valid_names: typing.List[str], k: typing.Optional[int], max_validations: int, default: typing.Optional[typing.List[int]], send_to: str, stream: bool, top_p: typing.Optional[float], temperature: typing.Optional[float], max_completion_tokens: typing.Optional[int], presence_penalty: typing.Optional[float], frequency_penalty: typing.Optional[float], no_cache: bool) -> typing.Awaitable[typing.Union[typing.Optional[typing.List[int]], typing.List[typing.Optional[typing.List[int]]]]]: ...
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
