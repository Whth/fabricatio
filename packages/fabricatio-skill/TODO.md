# TODO

- [x] Add Texts-based skill system, as a subpackage
    - [x] Skill YAML/JSON schema + loader + directory scanner
    - [x] Wire into Role + validation + example skill file + tests
- [x] Per-call skill-fetch cap: `select_skills`/`consult_skills(..., k=...)` (`None` = `max_selected_skills` config, `0` = no limit, `n` = at most n)
- [x] By-name skill gathering: `UseSkill.gather_skills` (`<root>/<name>/SKILL.md` then `<root>/<name>.md`; direct path reads, no corpus scan)
- [x] `~/.agents/skills` added to `default_skill_dirs` (auto-load + by-name roots; `~` expanded at use time)
- [x] Single process-wide skill library: `SkillRegistry.instance()` with `load_scanned`/`load_by_name` loaders returning the names they made available (the free functions are gone)
