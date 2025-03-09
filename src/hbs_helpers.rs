use handlebars::handlebars_helper;
use serde_json::Value;

handlebars_helper!(len: |v: Value| match v {
    Value::Array(arr) => arr.len(),
    Value::Object(obj) => obj.len(),
    Value::String(s) => s.len(),
    _ => 0
});