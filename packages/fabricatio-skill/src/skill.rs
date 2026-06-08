use pyo3::exceptions::PyFileNotFoundError;
use pyo3::prelude::*;
use rayon::prelude::*;
use serde::Deserialize;
use std::collections::HashMap;
use std::path::Path;
use std::sync::Mutex;
use walkdir::WalkDir;

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
fn parse_skill_file(raw: &str, relative_path: &str) -> Skill {
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

/// Scan a directory for `.md` skill files and return parsed Skill objects.
///
/// Walks the directory recursively, reads every `.md` file, parses YAML
/// frontmatter for metadata, and collects the markdown body as content.
///
/// Args:
///     path: Root directory to scan.
///
/// Returns:
///     List of Skill objects discovered from the directory.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
pub fn scan_skills(path: &str) -> PyResult<Vec<Skill>> {
    let root = Path::new(path);
    if !root.is_dir() {
        return Err(PyFileNotFoundError::new_err(format!(
            "Skill directory not found: {path}"
        )));
    }

    // Collect .md file paths first
    let entries: Vec<_> = WalkDir::new(root)
        .into_iter()
        .filter_map(|e| e.ok())
        .filter(|e| {
            e.file_type().is_file()
                && e.path()
                    .extension()
                    .is_some_and(|ext| ext.eq_ignore_ascii_case("md"))
        })
        .collect();

    // Read and parse in parallel
    let skills: Vec<Skill> = entries
        .par_iter()
        .filter_map(|entry| {
            let full_path = entry.path();
            let relative = full_path
                .strip_prefix(root)
                .ok()?
                .to_string_lossy()
                .replace('\\', "/");
            let raw = std::fs::read_to_string(full_path).ok()?;
            Some(parse_skill_file(&raw, &relative))
        })
        .collect();

    Ok(skills)
}

/// Search skills by keyword matching against name, description, tags, and content.
///
/// Args:
///     query: Search term (case-insensitive).
///     skills: List of skills to search through.
///     in_content: Whether to also search within the skill content body.
///
/// Returns:
///     Skills matching the query, ordered by relevance (name/tag match first).
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
#[pyo3(signature = (query, skills, in_content=false))]
pub fn search_skills(query: &str, skills: Vec<Skill>, in_content: bool) -> Vec<Skill> {
    let query_lower = query.to_lowercase();
    let query_terms: Vec<&str> = query_lower.split_whitespace().collect();

    if query_terms.is_empty() {
        return skills;
    }

    // Score each skill: higher = more relevant
    let mut scored: Vec<(usize, Skill)> = skills
        .into_par_iter()
        .filter_map(|skill| {
            let name_lower = skill.name.to_lowercase();
            let desc_lower = skill.description.to_lowercase();
            let tags_lower: Vec<String> = skill.tags.iter().map(|t| t.to_lowercase()).collect();

            let mut score: usize = 0;
            for term in &query_terms {
                // Name match (highest weight)
                if name_lower.contains(term) {
                    score += 10;
                }
                // Tag match (high weight)
                if tags_lower.iter().any(|t| t.contains(term)) {
                    score += 5;
                }
                // Description match (medium weight)
                if desc_lower.contains(term) {
                    score += 3;
                }
                // Content match (low weight, opt-in)
                if in_content && skill.content.to_lowercase().contains(term) {
                    score += 1;
                }
            }

            if score > 0 {
                Some((score, skill))
            } else {
                None
            }
        })
        .collect();

    // Sort by score descending
    scored.sort_by_key(|b| std::cmp::Reverse(b.0));
    scored.into_iter().map(|(_, skill)| skill).collect()
}

/// Get a skill by exact name.
///
/// Args:
///     name: Exact skill name to look up.
///     skills: List of skills to search.
///
/// Returns:
///     The matching Skill, or None if not found.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
pub fn get_skill(name: &str, skills: Vec<Skill>) -> Option<Skill> {
    skills.into_iter().find(|s| s.name == name)
}

/// Process-wide registry that owns all loaded ``Skill`` objects.
///
/// Python roles store skill **names** (plain ``str``) and resolve real
/// ``Skill`` objects through this registry at runtime.
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass]
pub struct SkillRegistry {
    store: Mutex<HashMap<String, Skill>>,
}

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl SkillRegistry {
    #[new]
    fn new() -> Self {
        Self {
            store: Mutex::new(HashMap::new()),
        }
    }

    /// Register skills. Returns count of newly added entries.
    fn register(&self, skills: Vec<Skill>) -> usize {
        let mut store = self.store.lock().unwrap();
        let before = store.len();
        for s in skills {
            store.entry(s.name.clone()).or_insert(s);
        }
        store.len() - before
    }

    /// Remove skills by name. Returns count removed.
    fn unregister(&self, names: Vec<String>) -> usize {
        let mut store = self.store.lock().unwrap();
        names.iter().filter(|n| store.remove(*n).is_some()).count()
    }

    /// Remove all registered skills.
    fn clear(&self) {
        self.store.lock().unwrap().clear();
    }

    /// Return a skill by exact name, or ``None``.
    fn get(&self, name: &str) -> Option<Skill> {
        self.store.lock().unwrap().get(name).cloned()
    }

    /// Return skills for the given names, silently skipping missing.
    fn get_many(&self, names: Vec<String>) -> Vec<Skill> {
        let store = self.store.lock().unwrap();
        names.iter().filter_map(|n| store.get(n).cloned()).collect()
    }

    /// Return every registered skill.
    fn all(&self) -> Vec<Skill> {
        self.store.lock().unwrap().values().cloned().collect()
    }

    /// Return every registered skill name.
    fn names(&self) -> Vec<String> {
        self.store.lock().unwrap().keys().cloned().collect()
    }

    fn __contains__(&self, name: &str) -> bool {
        self.store.lock().unwrap().contains_key(name)
    }

    fn __len__(&self) -> usize {
        self.store.lock().unwrap().len()
    }

    fn __repr__(&self) -> String {
        format!("SkillRegistry({} skills)", self.store.lock().unwrap().len())
    }
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Skill>()?;
    m.add_class::<SkillMeta>()?;
    m.add_class::<SkillRegistry>()?;
    m.add_function(wrap_pyfunction!(scan_skills, m)?)?;
    m.add_function(wrap_pyfunction!(search_skills, m)?)?;
    m.add_function(wrap_pyfunction!(get_skill, m)?)?;
    Ok(())
}
