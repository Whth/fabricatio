# TODO

- [x] Add Texts-based skill system, as a subpackage
    - [x] Skill YAML/JSON schema + loader + directory scanner
    - [x] Wire into Role + validation + example skill file + tests
- [x] Per-call skill-fetch cap: `select_skills`/`consult_skills(..., k=...)` (`None` = `max_selected_skills` config, `0` = no limit, `n` = at most n)
