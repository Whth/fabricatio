//! The process-wide skill library, and the Python-facing registry that loads it and
//! queries it.

use fabricatio_logger::{info, warn};
use parking_lot::Mutex;
use pyo3::exceptions::PyFileNotFoundError;
use pyo3::prelude::*;
use std::collections::BTreeMap;
use std::path::PathBuf;
use std::sync::LazyLock;

#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

use crate::layout::SkillDir;
use crate::query::SkillQuery;
use crate::roots::{CROSS_CLIENT_SKILL_DIRS, expand_home, resolve_root};
use crate::skill::Skill;

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
    /// root resolves are skipped, so resolution itself never fails: a call
    /// whose names all miss returns an empty selection and the caller carries
    /// on. Unresolved names are reported here, in one warning naming every
    /// root that was searched — callers need no guard of their own.
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
    ///     already in the library is reported too, without being read again;
    ///     names no root resolves are left out.
    #[pyo3(signature = (names, roots=None, extra_skill_dirs=None))]
    fn load_by_name(
        &self,
        names: Vec<String>,
        roots: Option<Vec<String>>,
        extra_skill_dirs: Option<Vec<String>>,
    ) -> Vec<String> {
        let extra: Vec<String> = extra_skill_dirs.unwrap_or_default();
        let mut declared: Vec<String> = match &roots {
            None => CROSS_CLIENT_SKILL_DIRS
                .iter()
                .map(|root| (*root).to_string())
                .collect(),
            Some(roots) => roots.clone(),
        };
        for root in &extra {
            push_unique(&mut declared, root.clone());
        }
        let dirs: Vec<SkillDir> = declared
            .iter()
            .map(|root| SkillDir::new(expand_home(root).unwrap_or_else(|| PathBuf::from(root))))
            .collect();

        let mut loaded = Vec::new();
        let mut missing = Vec::new();
        {
            let mut store = STORE.lock();
            for name in names {
                if loaded.contains(&name) || missing.contains(&name) {
                    continue;
                }
                if store.contains_key(&name) {
                    push_unique(&mut loaded, name);
                } else if let Some(skill) = dirs.iter().find_map(|dir| dir.fetch(&name)) {
                    store.entry(name.clone()).or_insert(skill);
                    push_unique(&mut loaded, name);
                } else {
                    missing.push(name);
                }
            }
        }
        if !missing.is_empty() {
            let searched = if declared.is_empty() {
                "(no lookup roots)".to_string()
            } else {
                declared.join(", ")
            };
            warn!(
                "Unknown skill(s): {}. Searched: {}",
                missing.join(", "),
                searched
            );
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    fn write(path: &Path, raw: &str) {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).unwrap();
        }
        std::fs::write(path, raw).unwrap();
    }

    /// Build a skill from plain parts; the store test only reads the descriptions.
    fn skill(name: &str, description: &str) -> Skill {
        Skill {
            name: name.to_string(),
            description: description.to_string(),
            tags: Vec::new(),
            content: String::new(),
            path: format!("{name}.md"),
        }
    }

    #[test]
    fn canonical_names_keep_the_first_copy_of_a_name() {
        let mut store = BTreeMap::new();

        assert_eq!(
            canonical_names(vec![skill("a", "first")], &mut store),
            ["a"]
        );
        assert_eq!(
            canonical_names(
                vec![
                    skill("a", "second"),
                    skill("b", "other"),
                    skill("a", "third"),
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

    #[test]
    fn load_by_name_keeps_hits_and_leaves_unresolvable_names_out() {
        let root = std::env::temp_dir().join("fabricatio_skill_test_unknown_names");
        let absent = std::env::temp_dir().join("fabricatio_skill_test_unknown_names_absent");
        let _ = std::fs::remove_dir_all(&root);
        write(
            &root.join("resolved_only.md"),
            "---\nname: resolved_only\ndescription: hit\n---\nbody",
        );

        let registry = SkillRegistry::new();
        let found = registry.load_by_name(
            vec![
                "resolved_only".to_string(),
                "absent_one".to_string(),
                "absent_one".to_string(),
                "absent_two".to_string(),
            ],
            Some(vec![
                absent.to_string_lossy().into_owned(),
                root.to_string_lossy().into_owned(),
            ]),
            None,
        );

        assert_eq!(found, ["resolved_only"]);

        let all_missed =
            registry.load_by_name(vec!["absent_three".to_string()], None, Some(Vec::new()));
        assert!(
            all_missed.is_empty(),
            "an all-miss selection is empty, not an error: {all_missed:?}"
        );

        std::fs::remove_dir_all(&root).unwrap();
    }
}
