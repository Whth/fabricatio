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

handlebars_helper!(code: |v:String,lang:String| format!(
    "```{lang}\n{v}\n```"
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

handlebars_helper!(timestamp_to_date: |v: u64| {
    chrono::DateTime::from_timestamp(v as i64, 0)
        .map(|dt| dt.format("%Y-%m-%d %H:%M:%S UTC").to_string())
        .unwrap_or_else(|| "Invalid timestamp".to_string())
});

handlebars_helper!(head: |v:String , n: i64| {
    let mut lines = v.lines();
    let mut result = String::new();
    let mut count = 0;
    for _ in 0..n {
        if let Some(line) = lines.next() {
            result.push_str(line);
            result.push('\n');
            count += 1;
        }
    }
    let total_lines = v.lines().count();
    if count < total_lines {
        result.push_str(&format!(".....\n(total {} lines hidden)\n", total_lines - count));
    }
    result.trim_end().to_string()

});
