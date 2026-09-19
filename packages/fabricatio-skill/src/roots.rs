//! Where skills are looked for: the cross-client roots, and how a configured root string
//! becomes a directory that exists right now.

use directories_next::BaseDirs;
use std::path::PathBuf;

use crate::layout::SkillDir;

/// The cross-client skill roots the library loads on its own.
///
/// The Agent Skills standard tells every host to read the project-local
/// `.agents/skills` and the user-level `~/.agents/skills`
/// (<https://agentskills.io/client-implementation/adding-skills-support>), so
/// skills installed by any compliant client are visible here. Client-specific
/// locations (`.claude/skills`, a bundled `skills/` dir, ...) are deliberately
/// not part of this list — `SkillRegistry` callers pass them per call, and
/// `skill_config.extra_skill_dirs` adds them process-wide.
pub(crate) const CROSS_CLIENT_SKILL_DIRS: [&str; 2] = [".agents/skills", "~/.agents/skills"];

/// Expand a leading `~` to the current user's home directory.
///
/// The home comes from the platform ([`BaseDirs::home_dir`]) — the same lookup
/// the configuration side resolves the roaming profile with — so `~` means one
/// thing across the workspace: the profile folder on Windows, `$HOME`
/// elsewhere. `None` when `raw` has no leading `~` (nothing to expand), names
/// another user (`~other`), or the platform reports no home directory.
pub(crate) fn expand_home(raw: &str) -> Option<PathBuf> {
    let rest = raw.strip_prefix('~')?;
    if !rest.is_empty() && !rest.starts_with(['/', '\\']) {
        return None;
    }
    let base = BaseDirs::new()?;
    let home = base.home_dir();
    let rest = rest.trim_start_matches(['/', '\\']);
    Some(if rest.is_empty() {
        home.to_path_buf()
    } else {
        home.join(rest)
    })
}

/// Resolve one configured root to a directory that exists right now.
///
/// `~` is expanded and the result probed; `None` marks a root to skip, which
/// is the ordinary case for the conventional dirs (most projects have no
/// `.agents/skills`).
pub(crate) fn resolve_root(raw: &str) -> Option<PathBuf> {
    let root = expand_home(raw).unwrap_or_else(|| PathBuf::from(raw));
    SkillDir::new(&root).is_dir().then_some(root)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn expand_home_leaves_non_home_paths_alone() {
        for raw in [".agents/skills", "skills", "/abs/skills", "~other/skills"] {
            assert!(expand_home(raw).is_none(), "raw: {raw}");
        }
    }

    #[test]
    fn expand_home_joins_onto_the_platform_home_directory() {
        let base = BaseDirs::new().expect("the platform reports base dirs");
        let home = base.home_dir();

        assert_eq!(expand_home("~"), Some(home.to_path_buf()));
        assert_eq!(expand_home("~/"), Some(home.to_path_buf()));
        assert_eq!(
            expand_home("~/.agents/skills"),
            Some(home.join(".agents/skills"))
        );
        assert_eq!(expand_home("~\\skills"), Some(home.join("skills")));
    }
}
