use log::{debug, error};
use regex::Regex;
use tex2typst_rs::tex2typst;

// Unified function to convert all supported TeX math expressions to Typst format
pub fn convert_all_tex_math(string: &str) -> Result<String, Box<dyn std::error::Error>> {
    // Regex to find TeX math expressions. Order matters: $$ before $, \[ before \(, etc.
    // This captures:
    // 1. $$...$$ (block) -> groups 1, 2, 3
    // 2. \[...\] (block) -> groups 4, 5, 6
    // 3. \(...\) (inline) -> groups 7, 8, 9
    // 4. $...$ (inline) -> groups 10, 11, 12 (must be careful not to match parts of $$)
    // The regex engine processes alternatives from left to right.
    // By placing more specific/longer delimiters first (e.g., $$ before $),
    // we ensure correct matching.
    let re =
        Regex::new(r"(?s)(\$\$)(.*?)(\$\$)|(\\\[)(.*?)(\\\])|(\\\()(.*?)(\\\))|(\$)(.*?)(\$)")?;

    let result = re.replace_all(string, |caps: &regex::Captures| {
        let (tex_code, is_block, original_wrapper_open, original_wrapper_close) =
            if let (Some(open), Some(content), Some(close)) =
                (caps.get(1), caps.get(2), caps.get(3))
            {
                (content.as_str(), true, open.as_str(), close.as_str()) // Matched $$...$$
            } else if let (Some(open), Some(content), Some(close)) =
                (caps.get(4), caps.get(5), caps.get(6))
            {
                (content.as_str(), true, open.as_str(), close.as_str()) // Matched \[...\]
            } else if let (Some(open), Some(content), Some(close)) =
                (caps.get(7), caps.get(8), caps.get(9))
            {
                (content.as_str(), false, open.as_str(), close.as_str()) // Matched \(...\)
            } else if let (Some(open), Some(content), Some(close)) =
                (caps.get(10), caps.get(11), caps.get(12))
            {
                (content.as_str(), false, open.as_str(), close.as_str()) // Matched $...$
            } else {
                // This case should ideally not be reached if the regex is comprehensive
                // and correctly structured for the input.
                // Return the original match if no known pattern is identified.
                return caps.get(0).unwrap().as_str().to_string();
            };

        match tex2typst(tex_code) {
            Ok(converted) => {
                let typst_math = if is_block {
                    format!("$\n{}\n$", converted.trim())
                } else {
                    format!(" ${}$ ", converted.trim())
                };
                debug!(
                    "Converting TeX: {}{}{} ==> Typst: {}",
                    original_wrapper_open,
                    tex_code,
                    original_wrapper_close,
                    typst_math.trim()
                );
                typst_math
            }
            Err(e) => {
                error!(
                    "Error converting TeX content (preserving original {} {} {}): {} -> {}",
                    original_wrapper_open, tex_code, original_wrapper_close, tex_code, e
                );
                // Preserve original TeX with original wrappers on error
                format!(
                    "{}{}{}",
                    original_wrapper_open, tex_code, original_wrapper_close
                )
            }
        }
    });
    Ok(result.into_owned())
}
