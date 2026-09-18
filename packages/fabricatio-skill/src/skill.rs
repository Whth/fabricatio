use pyo3::exceptions::PyFileNotFoundError;
use pyo3::prelude::*;
use rayon::prelude::*;
use serde::Deserialize;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
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

    /// Briefing of the skill: ``name: description``, used as an LLM option summary.
    #[getter]
    fn briefing(&self) -> String {
        if self.description.is_empty() {
            self.name.clone()
        } else {
            format!("{}: {}", self.name, self.description)
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

/// A file layout a skill may use inside a [`SkillDir`].
#[derive(Clone, Copy)]
enum SkillLayout {
    /// agent-skills convention: `<root>/<name>/SKILL.md`
    Dir,
    /// Flat convention: `<root>/<name>.md`
    Flat,
}

impl SkillLayout {
    /// Resolution order: the directory convention wins over the flat one.
    const ALL: [Self; 2] = [Self::Dir, Self::Flat];

    /// Path holding the skill named `name` under `root` in this layout.
    fn path(self, root: &Path, name: &str) -> PathBuf {
        match self {
            Self::Dir => root.join(name).join("SKILL.md"),
            Self::Flat => root.join(format!("{name}.md")),
        }
    }
}

/// A skill root directory: resolves bare names and scans `.md` files.
///
/// Owns every path convention, so the Python-facing functions stay thin:
/// [`fetch`](Self::fetch) reads known [`SkillLayout`] paths directly (no walk),
/// while [`scan`](Self::scan) walks the whole root in parallel. Both share
/// [`load`](Self::load), which records paths relative to the root.
struct SkillDir {
    root: PathBuf,
}

impl SkillDir {
    /// Bind to a root directory; it need not exist until read or scanned.
    fn new(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }

    /// Whether the root currently exists as a directory.
    fn is_dir(&self) -> bool {
        self.root.is_dir()
    }

    /// Resolve a bare `name` through [`SkillLayout::ALL`] without walking.
    ///
    /// Returns `None` for non-plain names (empty, separators, dot components)
    /// and when no layout path holds a readable file.
    fn fetch(&self, name: &str) -> Option<Skill> {
        if !is_plain_name(name) {
            return None;
        }
        SkillLayout::ALL
            .into_iter()
            .find_map(|layout| self.load(&layout.path(&self.root, name)))
    }

    /// Load every `.md` file under the root as a skill, in parallel.
    fn scan(&self) -> Vec<Skill> {
        WalkDir::new(&self.root)
            .into_iter()
            .filter_map(|entry| entry.ok())
            .filter(|entry| entry.file_type().is_file() && is_markdown(entry.path()))
            .collect::<Vec<_>>()
            .par_iter()
            .filter_map(|entry| self.load(entry.path()))
            .collect()
    }

    /// Read and parse one skill file; `None` when it is not a readable file.
    fn load(&self, path: &Path) -> Option<Skill> {
        let raw = std::fs::read_to_string(path).ok()?;
        Some(parse_skill_file(&raw, &self.relative(path)))
    }

    /// `path` relative to the root, slash-normalized (`herdr/SKILL.md`).
    fn relative(&self, path: &Path) -> String {
        path.strip_prefix(&self.root)
            .unwrap_or(path)
            .to_string_lossy()
            .replace('\\', "/")
    }
}

/// Whether `name` is a bare skill name: non-empty, no separators, no dot components.
fn is_plain_name(name: &str) -> bool {
    !name.is_empty() && !name.contains(['/', '\\']) && name != "." && name != ".."
}

/// Whether `path` carries the `.md` extension skill files use.
fn is_markdown(path: &Path) -> bool {
    path.extension()
        .is_some_and(|ext| ext.eq_ignore_ascii_case("md"))
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
    let dir = SkillDir::new(path);
    if !dir.is_dir() {
        return Err(PyFileNotFoundError::new_err(format!(
            "Skill directory not found: {path}"
        )));
    }
    Ok(dir.scan())
}

/// Fetch a single skill by name from a skill directory without scanning.
///
/// Tries the agent-skills convention `<root>/<name>/SKILL.md` first, then the
/// flat convention `<root>/<name>.md`. Direct path reads only — no directory walk.
///
/// Args:
///     root: Skill directory root to resolve the name against.
///     name: Skill name to fetch (a plain name; path separators are rejected).
///
/// Returns:
///     The parsed Skill, or None when no convention path holds a readable
///     `.md` file for this name.
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
pub fn fetch_skill(root: &str, name: &str) -> Option<Skill> {
    SkillDir::new(root).fetch(name)
}

/// A searchable field of a [`Skill`], checked for every query term.
#[derive(Clone, Copy)]
enum SkillField {
    /// Skill name (strongest signal).
    Name,
    /// Skill tags.
    Tags,
    /// Skill description.
    Description,
    /// Skill body (weakest signal, opt-in).
    Content,
}

impl SkillField {
    /// Fields matched against each term, strongest signal first.
    const ALL: [Self; 4] = [Self::Name, Self::Tags, Self::Description, Self::Content];

    /// Score added when a term matches this field.
    fn weight(self) -> usize {
        match self {
            Self::Name => 10,
            Self::Tags => 5,
            Self::Description => 3,
            Self::Content => 1,
        }
    }
}

/// A candidate skill prepared for matching: every searchable field lowercased once.
struct SearchableSkill {
    skill: Skill,
    name: String,
    description: String,
    tags: Vec<String>,
    /// Lowercased body; `None` while content search is disabled.
    content: Option<String>,
}

impl SearchableSkill {
    /// Lowercase the searchable fields; the body only when `in_content`.
    fn new(skill: Skill, in_content: bool) -> Self {
        Self {
            name: skill.name.to_lowercase(),
            description: skill.description.to_lowercase(),
            tags: skill.tags.iter().map(|tag| tag.to_lowercase()).collect(),
            content: in_content.then(|| skill.content.to_lowercase()),
            skill,
        }
    }

    /// Whether the lowercased `term` occurs in `field`.
    fn matches(&self, field: SkillField, term: &str) -> bool {
        match field {
            SkillField::Name => self.name.contains(term),
            SkillField::Tags => self.tags.iter().any(|tag| tag.contains(term)),
            SkillField::Description => self.description.contains(term),
            SkillField::Content => self
                .content
                .as_ref()
                .is_some_and(|body| body.contains(term)),
        }
    }
}

/// A parsed keyword query, scored against candidate skills.
struct SkillQuery {
    /// Lowercased whitespace-separated terms; an empty query matches everything.
    terms: Vec<String>,
    /// Whether [`SkillField::Content`] participates in matching.
    in_content: bool,
}

impl SkillQuery {
    /// Split `query` into lowercased terms.
    fn parse(query: &str, in_content: bool) -> Self {
        Self {
            terms: query
                .to_lowercase()
                .split_whitespace()
                .map(str::to_owned)
                .collect(),
            in_content,
        }
    }

    /// Weighted relevance of one candidate: the summed weights of every
    /// field each term matches.
    fn score(&self, skill: &SearchableSkill) -> usize {
        self.terms
            .iter()
            .map(|term| {
                SkillField::ALL
                    .iter()
                    .filter(|field| skill.matches(**field, term))
                    .map(|field| field.weight())
                    .sum::<usize>()
            })
            .sum()
    }

    /// Score all candidates in parallel; return matches by relevance, best first.
    ///
    /// An empty query returns `skills` untouched; skills scoring zero are dropped.
    fn search(&self, skills: Vec<Skill>) -> Vec<Skill> {
        if self.terms.is_empty() {
            return skills;
        }
        let mut scored: Vec<(usize, Skill)> = skills
            .into_par_iter()
            .filter_map(|skill| {
                let prepared = SearchableSkill::new(skill, self.in_content);
                let score = self.score(&prepared);
                (score > 0).then_some((score, prepared.skill))
            })
            .collect();
        // Stable sort: equal scores keep their input order.
        scored.sort_by_key(|(score, _)| std::cmp::Reverse(*score));
        scored.into_iter().map(|(_, skill)| skill).collect()
    }
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
    SkillQuery::parse(query, in_content).search(skills)
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
    m.add_function(wrap_pyfunction!(fetch_skill, m)?)?;
    m.add_function(wrap_pyfunction!(search_skills, m)?)?;
    m.add_function(wrap_pyfunction!(get_skill, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn write(path: &Path, raw: &str) {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).unwrap();
        }
        std::fs::write(path, raw).unwrap();
    }

    #[test]
    fn fetch_skill_dir_layout() {
        let root = std::env::temp_dir().join("fabricatio_skill_test_dir_layout");
        let _ = std::fs::remove_dir_all(&root);
        write(
            &root.join("herdr").join("SKILL.md"),
            "---\nname: herdr\ndescription: \"Terminal mux\"\ntags: [cli]\n---\n# Herdr\nbody",
        );

        let skill = fetch_skill(root.to_str().unwrap(), "herdr").expect("dir layout resolves");
        assert_eq!(skill.name, "herdr");
        assert_eq!(skill.description, "Terminal mux");
        assert_eq!(skill.tags, vec!["cli"]);
        assert_eq!(skill.content, "# Herdr\nbody");
        assert_eq!(skill.path, "herdr/SKILL.md");

        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn fetch_skill_flat_layout() {
        let root = std::env::temp_dir().join("fabricatio_skill_test_flat_layout");
        let _ = std::fs::remove_dir_all(&root);
        write(
            &root.join("code_review.md"),
            "---\nname: code_review\ndescription: Review code\n---\n# Review\nbody",
        );

        let skill =
            fetch_skill(root.to_str().unwrap(), "code_review").expect("flat layout resolves");
        assert_eq!(skill.name, "code_review");
        assert_eq!(skill.path, "code_review.md");

        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn fetch_skill_dir_layout_wins_over_flat() {
        let root = std::env::temp_dir().join("fabricatio_skill_test_precedence");
        let _ = std::fs::remove_dir_all(&root);
        write(
            &root.join("dual").join("SKILL.md"),
            "---\nname: dual\ndescription: from dir\n---\ndir body",
        );
        write(
            &root.join("dual.md"),
            "---\nname: dual\ndescription: from flat\n---\nflat body",
        );

        let skill = fetch_skill(root.to_str().unwrap(), "dual").expect("resolves");
        assert_eq!(skill.description, "from dir");

        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn fetch_skill_missing_returns_none() {
        let root = std::env::temp_dir().join("fabricatio_skill_test_missing");
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();

        assert!(fetch_skill(root.to_str().unwrap(), "nope").is_none());

        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn fetch_skill_rejects_path_like_names() {
        let root = std::env::temp_dir().join("fabricatio_skill_test_traversal");
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();

        for name in ["", ".", "..", "a/b", "a\\b", "../../evil"] {
            assert!(
                fetch_skill(root.to_str().unwrap(), name).is_none(),
                "name: {name}"
            );
        }

        std::fs::remove_dir_all(&root).unwrap();
    }

    /// Build a skill from plain parts; search tests place the term in one field each.
    fn skill(name: &str, description: &str, tags: &[&str], content: &str) -> Skill {
        Skill {
            name: name.to_string(),
            description: description.to_string(),
            tags: tags.iter().map(|tag| tag.to_string()).collect(),
            content: content.to_string(),
            path: format!("{name}.md"),
        }
    }

    #[test]
    fn search_skills_ranks_name_then_tags_then_description_then_content() {
        let skills = vec![
            skill("content_hit", "", &[], "needle in the body"),
            skill("description_hit", "needle in the description", &[], ""),
            skill("tag_hit", "", &["needle"], ""),
            skill("needle", "", &[], ""),
        ];

        let hits = search_skills("needle", skills, true);
        let names: Vec<&str> = hits.iter().map(|s| s.name.as_str()).collect();

        assert_eq!(
            names,
            vec!["needle", "tag_hit", "description_hit", "content_hit"]
        );
    }

    #[test]
    fn search_skills_blank_query_returns_all_untouched() {
        let skills = vec![skill("a", "", &[], ""), skill("b", "", &[], "")];

        assert_eq!(search_skills("   ", skills, false).len(), 2);
    }
}
