use fabricatio_logger::info;
use parking_lot::Mutex;
use pyo3::exceptions::PyFileNotFoundError;
use pyo3::prelude::*;
use rayon::prelude::*;
use serde::Deserialize;
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::LazyLock;
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

/// The cross-client skill roots the library loads on its own.
///
/// The Agent Skills standard tells every host to read the project-local
/// `.agents/skills` and the user-level `~/.agents/skills`
/// (<https://agentskills.io/client-implementation/adding-skills-support>), so
/// skills installed by any compliant client are visible here. Client-specific
/// locations (`.claude/skills`, a bundled `skills/` dir, ...) are deliberately
/// not part of this list — `SkillRegistry` callers pass them per call, and
/// `skill_config.extra_skill_dirs` adds them process-wide.
const CROSS_CLIENT_SKILL_DIRS: [&str; 2] = [".agents/skills", "~/.agents/skills"];

/// Expand a leading `~` to the current user's home directory.
///
/// Mirrors `pathlib`'s expansion so a configured root means the same thing on
/// both sides of the boundary: `USERPROFILE` wins, then `HOME`, then the
/// `HOMEDRIVE` + `HOMEPATH` pair Windows shells export. `None` when `raw` has
/// no leading `~`, names another user (`~other`), or no home is known.
fn expand_home(raw: &str) -> Option<PathBuf> {
    let rest = raw.strip_prefix('~')?;
    if !rest.is_empty() && !rest.starts_with(['/', '\\']) {
        return None;
    }
    let home = ["USERPROFILE", "HOME"]
        .into_iter()
        .find_map(|var| std::env::var_os(var).filter(|value| !value.is_empty()).map(PathBuf::from))
        .or_else(|| {
            let drive = std::env::var_os("HOMEDRIVE").filter(|value| !value.is_empty())?;
            let path = std::env::var_os("HOMEPATH").filter(|value| !value.is_empty())?;
            let mut home = PathBuf::from(drive);
            home.push(path);
            Some(home)
        })?;
    let rest = rest.trim_start_matches(['/', '\\']);
    Some(if rest.is_empty() { home } else { home.join(rest) })
}

/// Resolve one configured root to a directory that exists right now.
///
/// `~` is expanded and the result probed; `None` marks a root to skip, which
/// is the ordinary case for the conventional dirs (most projects have no
/// `.agents/skills`).
fn resolve_root(raw: &str) -> Option<PathBuf> {
    let root = expand_home(raw).unwrap_or_else(|| PathBuf::from(raw));
    SkillDir::new(&root).is_dir().then_some(root)
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

/// The process-wide skill store: one in-memory copy per skill name.
///
/// Lives outside any instance, so every [`SkillRegistry`] handle — and
/// therefore every role in the process — shares the same parsed skills.
static STORE: LazyLock<Mutex<BTreeMap<String, Skill>>> =
    LazyLock::new(|| Mutex::new(BTreeMap::new()));

/// Insert `skills` into `store` (the first copy of a name wins) and return those names.
///
/// A name already in `store` is reported without being replaced or re-read, so
/// callers can tell which skills a load made available; duplicates collapse.
fn canonical_names(skills: Vec<Skill>, store: &mut BTreeMap<String, Skill>) -> Vec<String> {
    let mut names = Vec::new();
    for skill in skills {
        let name = skill.name.clone();
        store.entry(name.clone()).or_insert(skill);
        push_unique(&mut names, name);
    }
    names
}

/// Append `name` to `names` unless it is already there; the first occurrence wins.
fn push_unique(names: &mut Vec<String>, name: String) {
    if !names.contains(&name) {
        names.push(name);
    }
}

/// The process-wide skill library: one in-memory copy of every loaded skill.
///
/// Python roles store skill **names** (plain ``str``) and resolve real
/// ``Skill`` objects through this library at runtime. ``SkillRegistry()`` hands
/// out a handle to the library itself — every handle shares the same store, so
/// a skill file is parsed once per process — and the loaders return the names
/// they made available (a cached name is reported, never read again).
#[cfg_attr(feature = "stubgen", gen_stub_pyclass)]
#[pyclass]
pub struct SkillRegistry;

#[cfg_attr(feature = "stubgen", gen_stub_pymethods)]
#[pymethods]
impl SkillRegistry {
    /// The process-wide library. Every handle shares the same in-memory skills.
    #[new]
    fn new() -> Self {
        Self
    }

    /// Load every `.md` file found under each root into the library.
    ///
    /// Walks each root recursively and parses YAML frontmatter plus markdown
    /// body (`<root>/<name>/SKILL.md` and flat `<root>/<name>.md` both match);
    /// a name already in the library keeps its first copy.
    ///
    /// Args:
    ///     roots: Directories to scan.
    ///
    /// Returns:
    ///     The names those roots provide, ordered. A name already in the library
    ///     is reported too, without its file being read again.
    ///
    /// Raises:
    ///     FileNotFoundError: One of the roots is not an existing directory
    ///         (nothing is loaded in that case).
    fn load_scanned(&self, roots: Vec<String>) -> PyResult<Vec<String>> {
        let missing: Vec<&str> = roots
            .iter()
            .filter(|root| !SkillDir::new(*root).is_dir())
            .map(String::as_str)
            .collect();
        if !missing.is_empty() {
            return Err(PyFileNotFoundError::new_err(format!(
                "Skill directory not found: {}",
                missing.join(", ")
            )));
        }
        let mut found = Vec::new();
        for root in &roots {
            found.extend(SkillDir::new(root).scan());
        }
        Ok(canonical_names(found, &mut STORE.lock()))
    }

    /// Load the cross-client skill dirs, plus any extra dirs the caller configures.
    ///
    /// The cross-client roots ([`CROSS_CLIENT_SKILL_DIRS`]) load first — the
    /// project-local one, then the user-level one — followed by
    /// `extra_skill_dirs`, so the standard locations win on a name collision.
    /// Each root is expanded (`~` → the user's home) and probed on every call,
    /// so a machine that has none of them is a no-op rather than an error —
    /// unlike [`load_scanned`](Self::load_scanned), which fails loud on a root
    /// the caller passed explicitly.
    ///
    /// Args:
    ///     extra_skill_dirs: Additional roots to load after the cross-client
    ///         ones (``skill_config.extra_skill_dirs``); omit for none.
    ///
    /// Returns:
    ///     The names those roots made available, in root order.
    #[pyo3(signature = (extra_skill_dirs=None))]
    fn load_skill_dirs(&self, extra_skill_dirs: Option<Vec<String>>) -> Vec<String> {
        let extra: Vec<String> = extra_skill_dirs.unwrap_or_default();
        let roots: Vec<&str> = CROSS_CLIENT_SKILL_DIRS
            .iter()
            .copied()
            .chain(extra.iter().map(String::as_str))
            .collect();

        let mut found = Vec::new();
        for raw in roots {
            let Some(root) = resolve_root(raw) else {
                continue;
            };
            let skills = SkillDir::new(&root).scan();
            if skills.is_empty() {
                continue;
            }
            info!("Loaded {} skill(s) from skill dir '{}'", skills.len(), raw);
            found.extend(skills);
        }
        canonical_names(found, &mut STORE.lock())
    }

    /// Resolve each name through `roots` and load the hits into the library.
    ///
    /// Tries each root in order — `<root>/<name>/SKILL.md` first, then
    /// `<root>/<name>.md` (direct path reads, no directory walk). Names already
    /// in the library keep their first copy and are not read again; names no
    /// root resolves are skipped.
    ///
    /// Args:
    ///     names: Skill names to resolve; duplicates collapse.
    ///     roots: Lookup roots, tried in order. Omit to use the cross-client
    ///         skill dirs.
    ///     extra_skill_dirs: Additional roots tried after `roots`
    ///         (``skill_config.extra_skill_dirs``); omit for none.
    ///
    /// Returns:
    ///     The names that are now in the library, in argument order. A name
    ///     already in the library is reported too, without being read again.
    #[pyo3(signature = (names, roots=None, extra_skill_dirs=None))]
    fn load_by_name(
        &self,
        names: Vec<String>,
        roots: Option<Vec<String>>,
        extra_skill_dirs: Option<Vec<String>>,
    ) -> Vec<String> {
        let extra: Vec<String> = extra_skill_dirs.unwrap_or_default();
        let raw: Vec<&str> = match &roots {
            None => CROSS_CLIENT_SKILL_DIRS.iter().copied().collect(),
            Some(roots) => roots.iter().map(String::as_str).collect(),
        };
        let dirs: Vec<SkillDir> = raw
            .into_iter()
            .chain(extra.iter().map(String::as_str))
            .map(|root| SkillDir::new(expand_home(root).unwrap_or_else(|| PathBuf::from(root))))
            .collect();

        let mut store = STORE.lock();
        let mut loaded = Vec::new();
        for name in names {
            if loaded.contains(&name) {
                continue;
            }
            if store.contains_key(&name) {
                push_unique(&mut loaded, name);
                continue;
            }
            if let Some(skill) = dirs.iter().find_map(|dir| dir.fetch(&name)) {
                store.entry(name.clone()).or_insert(skill);
                push_unique(&mut loaded, name);
            }
        }
        loaded
    }

    /// Merge already-parsed skills into the library; the first copy of a name wins.
    ///
    /// Args:
    ///     skills: Skill objects to add.
    ///
    /// Returns:
    ///     The library, for chaining.
    fn add(&self, skills: Vec<Skill>) -> Self {
        canonical_names(skills, &mut STORE.lock());
        Self
    }

    /// Drop the named skills, so their files are read again on the next load.
    ///
    /// Args:
    ///     names: Skill names to drop.
    ///
    /// Returns:
    ///     The library, for chaining.
    fn remove(&self, names: Vec<String>) -> Self {
        let mut store = STORE.lock();
        for name in &names {
            store.remove(name);
        }
        Self
    }

    /// Drop every loaded skill.
    ///
    /// Returns:
    ///     The library, for chaining.
    fn clear(&self) -> Self {
        STORE.lock().clear();
        Self
    }

    /// Return a skill by exact name, or ``None``.
    fn get(&self, name: &str) -> Option<Skill> {
        STORE.lock().get(name).cloned()
    }

    /// Return skills for the given names, silently skipping missing ones.
    fn get_many(&self, names: Vec<String>) -> Vec<Skill> {
        let store = STORE.lock();
        names.iter().filter_map(|n| store.get(n).cloned()).collect()
    }

    /// Return every loaded skill, ordered by name.
    fn all(&self) -> Vec<Skill> {
        STORE.lock().values().cloned().collect()
    }

    /// Return every loaded skill name, ordered.
    fn names(&self) -> Vec<String> {
        STORE.lock().keys().cloned().collect()
    }

    /// Search the library by keyword against name, tags, description, and content.
    ///
    /// Args:
    ///     query: Search term (case-insensitive).
    ///     names: Restrict the search to these skill names. None searches every
    ///         loaded skill.
    ///     in_content: Whether to also search within the skill content body.
    ///
    /// Returns:
    ///     Matching skills, ordered by relevance (name/tag match first).
    #[pyo3(signature = (query, names=None, in_content=false))]
    fn search(&self, query: &str, names: Option<Vec<String>>, in_content: bool) -> Vec<Skill> {
        let candidates = match names {
            Some(names) => self.get_many(names),
            None => self.all(),
        };
        SkillQuery::parse(query, in_content).search(candidates)
    }

    fn __contains__(&self, name: &str) -> bool {
        STORE.lock().contains_key(name)
    }

    fn __len__(&self) -> usize {
        STORE.lock().len()
    }

    fn __repr__(&self) -> String {
        format!("SkillRegistry({} skills)", STORE.lock().len())
    }
}

pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Skill>()?;
    m.add_class::<SkillMeta>()?;
    m.add_class::<SkillRegistry>()?;
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
    fn dir_fetch_resolves_dir_layout() {
        let root = std::env::temp_dir().join("fabricatio_skill_test_dir_layout");
        let _ = std::fs::remove_dir_all(&root);
        write(
            &root.join("herdr").join("SKILL.md"),
            "---\nname: herdr\ndescription: \"Terminal mux\"\ntags: [cli]\n---\n# Herdr\nbody",
        );

        let skill = SkillDir::new(&root)
            .fetch("herdr")
            .expect("dir layout resolves");
        assert_eq!(skill.name, "herdr");
        assert_eq!(skill.description, "Terminal mux");
        assert_eq!(skill.tags, vec!["cli"]);
        assert_eq!(skill.content, "# Herdr\nbody");
        assert_eq!(skill.path, "herdr/SKILL.md");

        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn dir_fetch_resolves_flat_layout() {
        let root = std::env::temp_dir().join("fabricatio_skill_test_flat_layout");
        let _ = std::fs::remove_dir_all(&root);
        write(
            &root.join("code_review.md"),
            "---\nname: code_review\ndescription: Review code\n---\n# Review\nbody",
        );

        let skill = SkillDir::new(&root)
            .fetch("code_review")
            .expect("flat layout resolves");
        assert_eq!(skill.name, "code_review");
        assert_eq!(skill.path, "code_review.md");

        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn dir_fetch_dir_layout_wins_over_flat() {
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

        let skill = SkillDir::new(&root).fetch("dual").expect("resolves");
        assert_eq!(skill.description, "from dir");

        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn dir_fetch_missing_returns_none() {
        let root = std::env::temp_dir().join("fabricatio_skill_test_missing");
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();

        assert!(SkillDir::new(&root).fetch("nope").is_none());

        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn dir_fetch_rejects_path_like_names() {
        let root = std::env::temp_dir().join("fabricatio_skill_test_traversal");
        let _ = std::fs::remove_dir_all(&root);
        std::fs::create_dir_all(&root).unwrap();

        for name in ["", ".", "..", "a/b", "a\\b", "../../evil"] {
            assert!(SkillDir::new(&root).fetch(name).is_none(), "name: {name}");
        }

        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn canonical_names_keep_the_first_copy_of_a_name() {
        let mut store = BTreeMap::new();

        assert_eq!(
            canonical_names(vec![skill("a", "first", &[], "")], &mut store),
            ["a"]
        );
        assert_eq!(
            canonical_names(
                vec![
                    skill("a", "second", &[], ""),
                    skill("b", "other", &[], ""),
                    skill("a", "third", &[], ""),
                ],
                &mut store
            ),
            ["a", "b"]
        );

        assert_eq!(store.len(), 2);
        assert_eq!(store["a"].description, "first");
        assert_eq!(store["b"].description, "other");
    }

    #[test]
    fn expand_home_leaves_non_home_paths_alone() {
        for raw in [".agents/skills", "skills", "/abs/skills", "~other/skills"] {
            assert!(expand_home(raw).is_none(), "raw: {raw}");
        }
    }

    #[test]
    fn load_skill_dirs_loads_extras_and_skips_absent_roots() {
        let root = std::env::temp_dir().join("fabricatio_skill_test_extras");
        let missing = std::env::temp_dir().join("fabricatio_skill_test_extras_missing");
        let _ = std::fs::remove_dir_all(&root);
        let _ = std::fs::remove_dir_all(&missing);
        write(
            &root.join("conv").join("SKILL.md"),
            "---\nname: conv_extra_test\ndescription: extra root\n---\nbody",
        );

        let registry = SkillRegistry::new();
        let names = registry.load_skill_dirs(Some(vec![
            missing.to_string_lossy().into_owned(),
            root.to_string_lossy().into_owned(),
        ]));

        assert!(
            names.contains(&"conv_extra_test".to_string()),
            "the extra root must load: {names:?}"
        );

        std::fs::remove_dir_all(&root).unwrap();
    }

    #[test]
    fn load_by_name_resolves_through_extras() {
        let root = std::env::temp_dir().join("fabricatio_skill_test_extras_lookup");
        let _ = std::fs::remove_dir_all(&root);
        write(
            &root.join("extra_lookup_test.md"),
            "---\nname: extra_lookup_test\ndescription: by-name extra\n---\nbody",
        );

        let registry = SkillRegistry::new();
        let found = registry.load_by_name(
            vec!["extra_lookup_test".to_string()],
            None,
            Some(vec![root.to_string_lossy().into_owned()]),
        );

        assert_eq!(found, ["extra_lookup_test"]);

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
    fn skill_query_ranks_name_then_tags_then_description_then_content() {
        let skills = vec![
            skill("content_hit", "", &[], "needle in the body"),
            skill("description_hit", "needle in the description", &[], ""),
            skill("tag_hit", "", &["needle"], ""),
            skill("needle", "", &[], ""),
        ];

        let hits = SkillQuery::parse("needle", true).search(skills);
        let names: Vec<&str> = hits.iter().map(|s| s.name.as_str()).collect();

        assert_eq!(
            names,
            vec!["needle", "tag_hit", "description_hit", "content_hit"]
        );
    }

    #[test]
    fn skill_query_blank_query_returns_all_untouched() {
        let skills = vec![skill("a", "", &[], ""), skill("b", "", &[], "")];

        assert_eq!(SkillQuery::parse("   ", false).search(skills).len(), 2);
    }
}
