//! Library for converting JSON Schema objects into Python function signatures and Google-style docstrings.
//!
//! This library parses a JSON Schema representing function parameters and generates the corresponding
//! Python type hints for the function signature and the `Args:` section of a Google-style docstring.
//! It strictly adheres to the convention that all non-required parameters are typed as `Optional[T] = None`
//! in both the signature and the docstring.

use heck::ToSnakeCase;
// For sorted_by_key and other iterator utilities
use serde::Deserialize;
use serde_json::Value;
use std::collections::HashSet;

// --- Data Structures for JSON Schema Parsing ---

/// Represents a parsed JSON Schema object relevant to function parameters.
#[derive(Deserialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
struct JsonSchema {
    /// Map of parameter names to their schema definitions.
    #[serde(default)]
    properties: serde_json::Map<String, Value>,
    /// list of parameter names that are required.
    #[serde(default)]
    required: Vec<String>,
    // Other fields like 'type' or 'additionalProperties' could be added for stricter validation
}

/// Holds processed information about a single function parameter.
#[derive(Debug, Clone)]
struct ParameterInfo {
    /// The parameter name converted to Python's snake_case convention.
    name: String,
    /// The base Python type (e.g., "str", "list[str]", "bool").
    base_py_type: String,
    /// The description of the parameter from the schema.
    description: String,
    /// Indicates if the parameter is required.
    is_required: bool,
    /// Optional list of allowed string values if the parameter is an enum.
    allowed_values: Option<Vec<String>>,
}

// --- Type Mapping Logic ---

/// Maps a JSON Schema type string and its definition to a Python type string.
fn map_json_type_to_python(json_type: &str, prop_obj: &serde_json::Map<String, Value>) -> String {
    match json_type {
        "string" => "str".to_string(),
        "number" => "float".to_string(),
        "integer" => "int".to_string(),
        "boolean" => "bool".to_string(),
        "array" => {
            let items_type_str = prop_obj
                .get("items")
                .and_then(|items| items.as_object())
                .and_then(|items_obj| items_obj.get("type"))
                .and_then(|t| t.as_str())
                .map(map_item_type_to_python)
                .unwrap_or_else(|| "object".to_string());
            format!("list[{}]", items_type_str)
        }
        "object" => "dict[str, object]".to_string(),
        _ => json_type.to_string(), // Fallback for unknown or custom types
    }
}

/// Maps a JSON Schema item type string (found within an `array` type's `items`) to a Python type string.
fn map_item_type_to_python(json_item_type: &str) -> String {
    match json_item_type {
        "string" => "str".to_string(),
        "number" => "float".to_string(),
        "integer" => "int".to_string(),
        "boolean" => "bool".to_string(),
        "array" => "list".to_string(),  // Simplified for nested arrays
        "object" => "dict".to_string(), // Simplified for nested objects
        _ => "object".to_string(),      // Fallback for complex or unspecified item types
    }
}

// --- Core Conversion Logic ---

/// Extracts ParameterInfo structs from the schema, ordered: required first (in "required" array order), then optional (in properties order).
fn extract_parameter_infos(schema: &JsonSchema) -> Vec<ParameterInfo> {
    let required_set: HashSet<&String> = schema.required.iter().collect();
    let mut ordered = Vec::new();
    // 1. Required
    for req_name in &schema.required {
        if let Some((original_name, prop_value)) = schema.properties.get_key_value(req_name)
            && let Some(param_info) =
                process_property(&original_name.to_snake_case(), prop_value, true)
        {
            ordered.push(param_info);
        }
    }
    // 2. Optional
    for (original_name, prop_value) in &schema.properties {
        if !required_set.contains(original_name)
            && let Some(param_info) =
                process_property(&original_name.to_snake_case(), prop_value, false)
        {
            ordered.push(param_info);
        }
    }
    ordered
}

fn format_signature_param(param_info: &ParameterInfo) -> String {
    if param_info.is_required {
        format!("{}: {}", param_info.name, param_info.base_py_type)
    } else {
        format!(
            "{}: Optional[{}] = None",
            param_info.name, param_info.base_py_type
        )
    }
}

fn format_docstring_arg(param_info: &ParameterInfo) -> String {
    let docstring_type = if param_info.is_required {
        param_info.base_py_type.clone()
    } else {
        format!("Optional[{}]", param_info.base_py_type)
    };
    let mut line = format!("    {}: {}", param_info.name, docstring_type);
    if !param_info.description.is_empty() {
        line.push_str(&format!(": {}", param_info.description.trim()));
    }
    if param_info.is_required {
        line.push_str(" (required)");
    }
    if let Some(values) = &param_info.allowed_values {
        line.push_str(&format!(" (allowed values: {})", values.join(", ")));
    }
    line
}

/// Generates a Python function signature string from a JSON Schema.
///
/// # Arguments
/// * `schema_value`: A `serde_json::Value` representing the JSON Schema.
///
/// # Returns
/// * `Some(String)`: The generated Python signature string (e.g., "(param1: Type1, param2: Optional[Type2] = None)").
/// * `None`: If the input schema is invalid or not an object schema.
pub fn schema_to_signature(schema_value: &Value) -> Option<String> {
    let schema: JsonSchema = serde_json::from_value(schema_value.clone()).ok()?;
    let infos = extract_parameter_infos(&schema);
    let mut param_strings: Vec<String> = infos.iter().map(format_signature_param).collect();
    if !param_strings.is_empty() {
        param_strings.insert(0, "*".to_string());
    }
    Some(format!("({})", param_strings.join(", ")))
}

/// Generates the `Args:` section of a Google-style Python docstring from a JSON Schema.
///
/// # Arguments
/// * `schema_value`: A `serde_json::Value` representing the JSON Schema.
///
/// # Returns
/// * `Some(String)`: The generated docstring `Args:` section.
/// * `None`: If the input schema is invalid, not an object schema, or has no properties.
pub fn schema_to_docstring_args(schema_value: &Value) -> Option<String> {
    let schema: JsonSchema = serde_json::from_value(schema_value.clone()).ok()?;
    if schema.properties.is_empty() {
        return None;
    }
    let infos = extract_parameter_infos(&schema);
    let args_lines: Vec<String> = infos.iter().map(format_docstring_arg).collect();
    if args_lines.is_empty() {
        None
    } else {
        Some(format!("Args:\n{}", args_lines.join("\n")))
    }
}

/// Processes a single property definition from the JSON Schema.
///
/// This function extracts the base type, description, and enum values.
///
/// # Arguments
/// * `snake_name`: The parameter name already converted to snake_case.
/// * `prop_value`: The `serde_json::Value` representing the property's schema.
/// * `is_required`: A boolean indicating if this property is required.
///
/// # Returns
/// * `Some(ParameterInfo)`: The processed information for the parameter.
/// * `None`: If the property definition is invalid or missing a type.
fn process_property(
    snake_name: &str,
    prop_value: &Value,
    is_required: bool,
) -> Option<ParameterInfo> {
    let prop_obj = prop_value.as_object()?;
    let json_type = prop_obj.get("type")?.as_str()?;

    let base_py_type = map_json_type_to_python(json_type, prop_obj);

    let description = prop_obj
        .get("description")
        .and_then(|d| d.as_str())
        .unwrap_or("")
        .to_string();

    let allowed_values = if json_type == "string" {
        prop_obj
            .get("enum")
            .and_then(|e| e.as_array())
            .map(|enum_array| {
                enum_array
                    .iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect()
            })
    } else {
        None
    };

    Some(ParameterInfo {
        name: snake_name.to_string(),
        base_py_type,
        description,
        is_required,
        allowed_values,
    })
}

// --- Tests ---
// (Tests remain functionally the same and should still pass)
#[cfg(test)]
mod tests {
    use super::*;
    use indoc::indoc;
    use serde_json::json;

    // Helper to create schema JSON for tests
    fn schema_from_props_and_required(
        properties: serde_json::Map<String, Value>,
        required: Vec<&str>,
    ) -> Value {
        json!({
            "$schema": "http://json-schema.org/draft-07/schema#",
            "additionalProperties": false,
            "properties": properties,
            "required": required,
            "type": "object"
        })
    }
    #[test]
    fn test_blank_schema() {
        let schema_value = json!({"$schema":"http://json-schema.org/draft-07/schema#","additionalProperties":false,"properties":{},"type":"object"});
        let signature = schema_to_signature(&schema_value);
        assert_eq!(signature, Some("()".to_string()));
        let docstring = schema_to_docstring_args(&schema_value);
        assert_eq!(docstring, None);
    }
    #[test]
    fn test_empty_schema() {
        let schema_value = schema_from_props_and_required(serde_json::Map::new(), vec![]);
        let signature = schema_to_signature(&schema_value);
        assert_eq!(signature, Some("()".to_string()));
        let docstring = schema_to_docstring_args(&schema_value);
        assert_eq!(docstring, None);
    }

    #[test]
    fn test_width_height_schema() {
        let mut properties = serde_json::Map::new();
        properties.insert(
            "height".to_string(),
            json!({"description": "Height of the browser window", "type": "number"}),
        );
        properties.insert(
            "width".to_string(),
            json!({"description": "Width of the browser window", "type": "number"}),
        );
        let schema_value = schema_from_props_and_required(properties, vec!["width", "height"]);

        let signature = schema_to_signature(&schema_value);
        assert_eq!(
            signature,
            Some("(*, width: float, height: float)".to_string())
        );

        let expected_docstring = indoc! {"
            Args:
                width: float: Width of the browser window (required)
                height: float: Height of the browser window (required)
        "}
        .trim_end();
        let docstring = schema_to_docstring_args(&schema_value);
        assert_eq!(docstring, Some(expected_docstring.to_string()));
    }

    #[test]
    fn test_accept_prompt_text_schema() {
        let mut properties = serde_json::Map::new();
        properties.insert(
            "accept".to_string(),
            json!({"description": "Whether to accept the dialog.", "type": "boolean"}),
        );
        properties.insert(
            "promptText".to_string(),
            json!({"description": "The text of the prompt in case of a prompt dialog.", "type": "string"}),
        );
        let schema_value = schema_from_props_and_required(properties, vec!["accept"]);

        let signature = schema_to_signature(&schema_value);
        assert_eq!(
            signature,
            Some("(*, accept: bool, prompt_text: Optional[str] = None)".to_string())
        );

        let expected_docstring = indoc! {"
            Args:
                accept: bool: Whether to accept the dialog. (required)
                prompt_text: Optional[str]: The text of the prompt in case of a prompt dialog.
        "}
        .trim_end();
        let docstring = schema_to_docstring_args(&schema_value);
        assert_eq!(docstring, Some(expected_docstring.to_string()));
    }

    #[test]
    fn test_click_schema_with_enum() {
        let mut properties = serde_json::Map::new();
        properties.insert(
            "button".to_string(),
            json!({
                "description": "Button to click, defaults to left",
                "enum": ["left", "right", "middle"],
                "type": "string"
            }),
        );
        properties.insert(
            "doubleClick".to_string(),
            json!({"description": "Whether to perform a double click instead of a single click", "type": "boolean"}),
        );
        properties.insert(
            "element".to_string(),
            json!({"description": "Human-readable element description used to obtain permission to interact with the element", "type": "string"}),
        );
        properties.insert(
            "ref".to_string(),
            json!({"description": "Exact target element reference from the page snapshot", "type": "string"}),
        );
        let schema_value = schema_from_props_and_required(properties, vec!["element", "ref"]);

        let signature = schema_to_signature(&schema_value);
        assert_eq!(signature, Some("(*, element: str, ref: str, button: Optional[str] = None, double_click: Optional[bool] = None)".to_string()));

        let expected_docstring = indoc! {r#"
            Args:
                element: str: Human-readable element description used to obtain permission to interact with the element (required)
                ref: str: Exact target element reference from the page snapshot (required)
                button: Optional[str]: Button to click, defaults to left (allowed values: left, right, middle)
                double_click: Optional[bool]: Whether to perform a double click instead of a single click
        "#}.trim_end();
        let docstring = schema_to_docstring_args(&schema_value);
        assert_eq!(docstring, Some(expected_docstring.to_string()));
    }

    #[test]
    fn test_screenshot_schema() {
        let mut properties = serde_json::Map::new();
        properties.insert(
            "element".to_string(),
            json!({"description": "Human-readable element description used to obtain permission to screenshot the element. If not provided, the screenshot will be taken of viewport. If element is provided, ref must be provided too.", "type": "string"}),
        );
        properties.insert(
            "filename".to_string(),
            json!({"description": "File name to save the screenshot to. Defaults to `page-{timestamp}.{png|jpeg}` if not specified.", "type": "string"}),
        );
        properties.insert(
            "fullPage".to_string(),
            json!({"description": "When true, takes a screenshot of the full scrollable page, instead of the currently visible viewport. Cannot be used with element screenshots.", "type": "boolean"}),
        );
        properties.insert(
            "raw".to_string(),
            json!({"description": "Whether to return without compression (in PNG format). Default is false, which returns a JPEG image.", "type": "boolean"}),
        );
        properties.insert(
            "ref".to_string(),
            json!({"description": "Exact target element reference from the page snapshot. If not provided, the screenshot will be taken of viewport. If ref is provided, element must be provided too.", "type": "string"}),
        );
        let schema_value = schema_from_props_and_required(properties, vec![]); // No required fields

        let signature = schema_to_signature(&schema_value);
        assert_eq!(signature, Some("(*, element: Optional[str] = None, filename: Optional[str] = None, full_page: Optional[bool] = None, raw: Optional[bool] = None, ref: Optional[str] = None)".to_string()));

        let expected_docstring = indoc! {"
            Args:
                element: Optional[str]: Human-readable element description used to obtain permission to screenshot the element. If not provided, the screenshot will be taken of viewport. If element is provided, ref must be provided too.
                filename: Optional[str]: File name to save the screenshot to. Defaults to `page-{timestamp}.{png|jpeg}` if not specified.
                full_page: Optional[bool]: When true, takes a screenshot of the full scrollable page, instead of the currently visible viewport. Cannot be used with element screenshots.
                raw: Optional[bool]: Whether to return without compression (in PNG format). Default is false, which returns a JPEG image.
                ref: Optional[str]: Exact target element reference from the page snapshot. If not provided, the screenshot will be taken of viewport. If ref is provided, element must be provided too.
        "}.trim_end();
        let docstring = schema_to_docstring_args(&schema_value);
        assert_eq!(docstring, Some(expected_docstring.to_string()));
    }

    #[test]
    fn test_file_upload_schema() {
        let mut properties = serde_json::Map::new();
        properties.insert(
            "paths".to_string(),
            json!({
                "description": "The absolute paths to the files to upload. Can be a single file or multiple files.",
                "items": {"type": "string"},
                "type": "array"
            }),
        );
        let schema_value = schema_from_props_and_required(properties, vec!["paths"]);

        let signature = schema_to_signature(&schema_value);
        assert_eq!(signature, Some("(*, paths: list[str])".to_string()));

        let expected_docstring = indoc! {"
            Args:
                paths: list[str]: The absolute paths to the files to upload. Can be a single file or multiple files. (required)
        "}.trim_end();
        let docstring = schema_to_docstring_args(&schema_value);
        assert_eq!(docstring, Some(expected_docstring.to_string()));
    }

    #[test]
    fn test_select_dropdown_schema() {
        let mut properties = serde_json::Map::new();
        properties.insert(
            "element".to_string(),
            json!({"description": "Human-readable element description used to obtain permission to interact with the element", "type": "string"}),
        );
        properties.insert(
            "ref".to_string(),
            json!({"description": "Exact target element reference from the page snapshot", "type": "string"}),
        );
        properties.insert(
            "values".to_string(),
            json!({
                 "description": "Array of values to select in the dropdown. This can be a single value or multiple values.",
                 "items": {"type": "string"},
                 "type": "array"
             }),
        );
        let schema_value =
            schema_from_props_and_required(properties, vec!["element", "ref", "values"]);

        let signature = schema_to_signature(&schema_value);
        assert_eq!(
            signature,
            Some("(*, element: str, ref: str, values: list[str])".to_string())
        );

        let expected_docstring = indoc! {"
            Args:
                element: str: Human-readable element description used to obtain permission to interact with the element (required)
                ref: str: Exact target element reference from the page snapshot (required)
                values: list[str]: Array of values to select in the dropdown. This can be a single value or multiple values. (required)
        "}.trim_end();
        let docstring = schema_to_docstring_args(&schema_value);
        assert_eq!(docstring, Some(expected_docstring.to_string()));
    }

    #[test]
    fn test_extract_parameter_info_handles_missing_type() {
        let prop_value: Value = json!({"description": "A param without type"});
        // This test now targets the lower-level function `process_property`
        let result = process_property("param", &prop_value, false);
        assert!(result.is_none());
    }

    #[test]
    fn test_extract_parameter_info_handles_non_object_property() {
        let prop_value: Value = json!("just_a_string");
        let result = process_property("param", &prop_value, false);
        assert!(result.is_none());
    }
}
