# TODO

- [x] Add Texts-based skill system, as a subpackage
    - [x] Skill YAML/JSON schema + loader + directory scanner
    - [x] Wire into Role + validation + example skill file + tests
- [x] Per-call skill-fetch cap: `select_skills`/`consult_skills(..., k=...)` (`None` = `max_selected_skills` config, `0` = no limit, `n` = at most n)
- [x] By-name skill gathering: `UseSkill.gather_skills` (`<root>/<name>/SKILL.md` then `<root>/<name>.md`; direct path reads, no corpus scan)
- [x] Cross-client skill roots fixed in Rust (`CROSS_CLIENT_SKILL_DIRS`: `.agents/skills`, then `~/.agents/skills`); `SkillRegistry.load_skill_dirs` loads them tolerantly (`~` expanded, absent roots skipped, per-root log) plus `skill_config.extra_skill_dirs`
- [x] Single process-wide skill library: `SkillRegistry()` handles over `load_scanned`/`load_by_name` loaders returning the names they made available (the free functions are gone)
- [x] `get_skill_registry()` (`@once`) creates the library already loaded; a role that tracked no names consults the whole library, so zero-config needs no load call and no per-role state
- [x] Cross-client skill dirs only by default: `.agents/skills` + `~/.agents/skills` (the location the Agent Skills standard tells hosts to scan) — client-specific roots are opt-in via `extra_skill_dirs`, `scan_skills`, or `dirs=`
