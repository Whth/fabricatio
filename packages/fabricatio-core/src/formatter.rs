#[inline]
pub fn generic_block_header(title: &str) -> String {
    format!("--- Start of {} ---", title)
}
#[inline]
pub fn generic_block_footer(title: &str) -> String {
    format!("--- End of {} ---", title)
}
pub fn generic_block(title: &str, value: &str) -> String {
    format!(
        "{}\n{}\n{}",
        generic_block_header(title),
        value,
        generic_block_footer(title)
    )
}

pub fn code_block(lang: &str, v: &str) -> String {
    format!("```{lang}\n{v}\n```")
}
