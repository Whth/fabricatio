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
    /// Markdown body (everything after the frontmatter), trimmed of the blank line around it.
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

/// Split raw file content into its YAML frontmatter block and the markdown body after it.
///
/// Frontmatter is delimited by `---` on its own line at the start of the file; a file
/// that opens with no such block has no frontmatter, and the caller then treats the
/// whole file as the body. Both halves come back trimmed of the whitespace the
/// delimiters leave around them, so a file authored with CRLF ends parses to the very
/// same bytes as an LF one.
fn split_front_matter(raw: &str) -> Option<(&str, &str)> {
    let rest = raw.strip_prefix("---")?;
    // The closing delimiter is the first `---` line after the opening one.
    let end = rest.find("\n---")?;
    Some((rest[..end].trim(), rest[end + 4..].trim()))
}

/// Parse YAML frontmatter + markdown body from raw file content.
/// Frontmatter is delimited by `---` on its own line at the start of the file.
pub(crate) fn parse_skill_file(raw: &str, relative_path: &str) -> Skill {
    let (fm, body) = match split_front_matter(raw) {
        Some((yaml_str, body)) => (serde_yaml2::from_str(yaml_str).unwrap_or_default(), body),
        None => (FrontMatter::default(), raw.trim()),
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
        content: body.to_string(),
        path: relative_path.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_reads_crlf_frontmatter_and_body() {
        let skill = parse_skill_file(
            "---\r\nname: lead\r\ndescription: lead house style\r\ntags: [writing]\r\n---\r\n\r\nKeep it short.\r\n",
            "lead/SKILL.md",
        );

        assert_eq!(skill.name, "lead");
        assert_eq!(skill.description, "lead house style");
        assert_eq!(skill.tags, ["writing"]);
        assert_eq!(skill.content, "Keep it short.");
        assert_eq!(skill.render(), "<lead>Keep it short.</lead>");
    }

    #[test]
    fn parse_reads_lf_frontmatter_and_body_alike() {
        let skill = parse_skill_file(
            "---\nname: lead\ndescription: lead house style\n---\n\nKeep it short.\n",
            "lead/SKILL.md",
        );

        assert_eq!(skill.name, "lead");
        assert_eq!(skill.content, "Keep it short.");
    }

    #[test]
    fn parse_without_frontmatter_names_the_skill_after_its_file() {
        let skill = parse_skill_file("Just a body.\n\n", "plain.md");

        assert_eq!(skill.name, "plain");
        assert_eq!(skill.description, "");
        assert_eq!(skill.content, "Just a body.");
    }

    #[test]
    fn parse_keeps_an_unclosed_frontmatter_block_as_the_body() {
        let skill = parse_skill_file("---\nname: lead\n\nNot frontmatter.\n", "lead/SKILL.md");

        assert_eq!(skill.name, "SKILL");
        assert_eq!(skill.content, "---\nname: lead\n\nNot frontmatter.");
    }
}
