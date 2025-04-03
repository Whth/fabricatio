use crate::language::convert_to_string_respectively;
use crate::word_split::word_count as wc;
use blake3::hash as blake3_hash;
use handlebars::handlebars_helper;
use serde_json::Value;
use whichlang::detect_language;
handlebars_helper!(len: |v: Value| match v {
    Value::Array(arr) => arr.len(),
    Value::Object(obj) => obj.len(),
    Value::String(s) => s.len(),
    _ => 0
});



handlebars_helper!(getlang: |v:String| convert_to_string_respectively(detect_language(v.as_str())));


handlebars_helper!(hash: |v:String| blake3_hash(v.as_bytes()).to_string());

handlebars_helper!(word_count: |v:String| wc(v));