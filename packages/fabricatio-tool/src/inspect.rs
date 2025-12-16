use ignore::WalkBuilder;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use std::collections::HashMap;
use std::path::PathBuf;

#[pyfunction]
#[pyo3(signature = (directory, max_depth = 8))]
/// Generates a tree-like string representation of a directory structure.
///
/// Skips hidden files and respects .gitignore.
///
/// # Arguments
///
/// * `directory`: Root path to visualize
/// * `max_depth`: Maximum depth to traverse (0 = root only, 1 = direct children, ...)
///
/// # Returns
///
/// A formatted string resembling the Unix `tree` command output.
pub fn treeview(directory: PathBuf, max_depth: usize) -> PyResult<String> {
    let dir = directory.canonicalize()?;
    let root_name = dir
        .file_name()
        .and_then(|s| s.to_str())
        .ok_or_else(|| PyValueError::new_err("Invalid directory path"))?
        .to_string();

    // Build walker
    let walker_entries: Vec<_> = WalkBuilder::new(&dir)
        .max_depth(Some(max_depth))
        .min_depth(Some(1))
        .follow_links(false)
        .build()
        .filter_map(Result::ok)
        .map(|entry| {
            let path = entry.path().to_path_buf();
            let depth = entry.depth();
            let name = path.file_name().unwrap().to_string_lossy().into_owned();
            let parent_key = path.parent().map(|p| p.to_path_buf());
            (depth, name, parent_key, path)
        })
        .collect();

    // Determine last entries for each parent directory
    let entries = if walker_entries.is_empty() {
        vec![]
    } else {
        let mut parent_last = HashMap::new();
        // Process in reverse to find last child of each parent
        walker_entries
            .iter()
            .rev()
            .for_each(|(depth, _, parent_key, path)| {
                let key = (parent_key.clone(), *depth);
                parent_last.entry(key).or_insert_with(|| path.clone());
            });

        // Create TreeEntry with correct is_last flags
        walker_entries
            .into_iter()
            .map(|(depth, name, parent_key, path)| {
                let key = (parent_key, depth);
                let is_last = parent_last
                    .get(&key)
                    .map(|last_path| last_path == &path)
                    .unwrap_or(false);
                TreeEntry {
                    depth,
                    name,
                    is_last,
                }
            })
            .collect()
    };

    let tree_lines = build_tree_lines(entries);

    Ok(format!("{root_name}\n{tree_lines}"))
}

/// Builds a tree-like string from a list of TreeEntry structs.
fn build_tree_lines(entries: Vec<TreeEntry>) -> String {
    let mut levels = Vec::new(); // For each level, whether to draw "│   "

    entries
        .into_iter()
        .map(|entry| {
            let depth = entry.depth;

            // Adjust levels vector to current depth
            if depth > levels.len() {
                // Extend levels with false (no bar) for new levels
                levels.resize(depth - 1, false);
            } else {
                // Shrink levels to current depth
                levels.truncate(depth - 1);
            }
            levels.push(!entry.is_last);

            // Build prefix with │ and spaces
            let prefix: String = levels[..depth - 1]
                .iter()
                .map(|&has_bar| if has_bar { "│ " } else { "  " })
                .collect();

            let connector = if entry.is_last { "└ " } else { "├ " };

            format!("{prefix}{connector}{}", entry.name)
        })
        .collect::<Vec<String>>()
        .join("\n")
}

struct TreeEntry {
    depth: usize,
    name: String,
    is_last: bool,
}

pub(crate) fn register(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(treeview, m)?)?;
    Ok(())
}
