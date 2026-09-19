//! How a skill sits inside a root directory: the two file conventions, and the reader
//! that fetches one by name or scans a whole root.

use rayon::prelude::*;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

use crate::skill::{Skill, parse_skill_file};

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
pub(crate) struct SkillDir {
    root: PathBuf,
}

impl SkillDir {
    /// Bind to a root directory; it need not exist until read or scanned.
    pub(crate) fn new(root: impl Into<PathBuf>) -> Self {
        Self { root: root.into() }
    }

    /// Whether the root currently exists as a directory.
    pub(crate) fn is_dir(&self) -> bool {
        self.root.is_dir()
    }

    /// Resolve a bare `name` through [`SkillLayout::ALL`] without walking.
    ///
    /// Returns `None` for non-plain names (empty, separators, dot components)
    /// and when no layout path holds a readable file.
    pub(crate) fn fetch(&self, name: &str) -> Option<Skill> {
        if !is_plain_name(name) {
            return None;
        }
        SkillLayout::ALL
            .into_iter()
            .find_map(|layout| self.load(&layout.path(&self.root, name)))
    }

    /// Load every `.md` file under the root as a skill, in parallel.
    pub(crate) fn scan(&self) -> Vec<Skill> {
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
}
