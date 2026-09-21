//! The skill model: what a loaded skill is, and how one is parsed out of a markdown file.

use pyo3::prelude::*;
use serde::Deserialize;
use std::path::Path;

#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

/// Metadata parsed from YAML frontmatter in a skill file.
#[derive(Deserialize, Default)]
struct FrontMatter {
    #[serde(default)]
    name: String,
    #[serde(default)]
    description: String,
    #[serde(default)]
    tags: Vec<String>,
}

/// A loaded skill: metadata + markdown content.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(from_py_object)]
#[derive(Clone)]
pub struct Skill {
    /// Skill identifier (from frontmatter `name`, or filename stem).
    #[pyo3(get)]
    pub name: String,
    /// Human-readable description.
    #[pyo3(get)]
    pub description: String,
    /// Tags for search/filtering.
    #[pyo3(get)]
    pub tags: Vec<String>,
    /// Markdown body (everything after the frontmatter).
    #[pyo3(get)]
    pub content: String,
    /// Source file path (relative to scan root).
    #[pyo3(get)]
    pub path: String,
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl Skill {
    #[new]
    fn new(
        name: String,
        description: String,
        tags: Vec<String>,
        content: String,
        path: String,
    ) -> Self {
        Self {
            name,
            description,
            tags,
            content,
            path,
        }
    }

    /// Briefing of the skill: ``name: description``, used as an LLM option summary.
    #[getter]
    fn briefing(&self) -> String {
        if self.description.is_empty() {
            self.name.clone()
        } else {
            format!("{}: {}", self.name, self.description)
        }
    }

    /// Render the skill as ``<name>content</name>``: the body wrapped in a tag named after it.
    fn render(&self) -> String {
        format!("<{}>{}</{}>", self.name, self.content, self.name)
    }

    /// Lightweight representation: name + description + tags (no content).
    fn meta(&self) -> SkillMeta {
        SkillMeta {
            name: self.name.clone(),
            description: self.description.clone(),
            tags: self.tags.clone(),
            path: self.path.clone(),
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "Skill(name='{}', tags={:?}, content_len={})",
            self.name,
            self.tags,
            self.content.len()
        )
    }
}

/// Lightweight skill metadata (no content body).
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass(from_py_object)]
#[derive(Clone)]
pub struct SkillMeta {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub description: String,
    #[pyo3(get)]
    pub tags: Vec<String>,
    #[pyo3(get)]
    pub path: String,
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl SkillMeta {
    fn __repr__(&self) -> String {
        format!("SkillMeta(name='{}', tags={:?})", self.name, self.tags)
    }
}

/// Parse YAML frontmatter + markdown body from raw file content.
/// Frontmatter is delimited by `---` on its own line at the start of the file.
pub(crate) fn parse_skill_file(raw: &str, relative_path: &str) -> Skill {
    let (fm, body) = if raw.starts_with("---") {
        // Find the closing ---
        let rest = &raw[3..];
        if let Some(end) = rest.find("\n---") {
            let yaml_str = &rest[..end];
            let body_start = end + 4; // skip "\n---"
            let body = rest[body_start..].trim_start_matches('\n').to_string();
            let fm: FrontMatter = serde_yaml2::from_str(yaml_str).unwrap_or_default();
            (fm, body)
        } else {
            (FrontMatter::default(), raw.to_string())
        }
    } else {
        (FrontMatter::default(), raw.to_string())
    };

    // Derive name from frontmatter or filename stem
    let name = if fm.name.is_empty() {
        Path::new(relative_path)
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("unnamed")
            .to_string()
    } else {
        fm.name
    };

    Skill {
        name,
        description: fm.description,
        tags: fm.tags,
        content: body,
        path: relative_path.to_string(),
    }
}
