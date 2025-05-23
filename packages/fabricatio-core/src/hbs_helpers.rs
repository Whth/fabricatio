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

handlebars_helper!(word_count: |v:String| wc(v.as_str()));

handlebars_helper!(block: |v:String,title:String| format!(
    "--- Start of `{title}` ---\n{v}\n--- End of `{title}` ---\n",
));

handlebars_helper!(list_out_string: |v: Vec<String>| {
    v.iter()
        .map(|s_item| {
            let mut lines_iter = s_item.lines();
            if let Some(first_line) = lines_iter.next() {
                let mut item_output = format!("- {first_line}");
                for subsequent_line in lines_iter {
                    item_output.push_str("\n  "); // Indent for subsequent lines
                    item_output.push_str(subsequent_line);
                }
                item_output.push('\n'); // Each list item ends with a newline
                item_output
            } else {
                // This handles cases where s_item is an empty string.
                // The original behavior for an empty string s was format!("- {s}\n"), resulting in "- \n".
                // "".lines() yields an empty iterator, so this branch is taken.
                "- \n".to_string()
            }
        })
        .collect::<String>()
});
