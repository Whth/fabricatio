/// Generates the header line for a generic block with the given title.
///
/// The header follows the format: "--- Start of {title} ---"
///
/// Args:
///     title: The title identifier for the generic block.
///
/// Returns:
///     A string representing the header line.
#[inline]
pub fn generic_block_header(title: &str) -> String {
    format!("--- Start of {} ---", title)
}

/// Generates the footer line for a generic block with the given title.
///
/// The footer follows the format: "--- End of {title} ---"
///
/// Args:
///     title: The title identifier for the generic block.
///
/// Returns:
///     A string representing the footer line.
#[inline]
pub fn generic_block_footer(title: &str) -> String {
    format!("--- End of {} ---", title)
}

/// Creates a complete generic block with header, content, and footer.
///
/// This function formats a value within a generic block structure,
/// typically used for separating content sections in prompts or templates.
///
/// Args:
///     title: The title identifier for the generic block.
///     value: The content to be enclosed within the block.
///
/// Returns:
///     A string containing the complete block with header, content, and footer.
pub fn generic_block(title: &str, value: &str) -> String {
    format!(
        "{}\n{}\n{}",
        generic_block_header(title),
        value,
        generic_block_footer(title)
    )
}

/// Creates a code block with syntax highlighting markers.
///
/// The code block is formatted with triple backticks and the specified language identifier.
///
/// Args:
///     lang: The programming language identifier for syntax highlighting.
///     v: The code content to be enclosed in the code block.
///
/// Returns:
///     A string representing the code block with language marker.
pub fn code_block(lang: &str, v: &str) -> String {
    format!("```{lang}\n{v}\n```")
}
