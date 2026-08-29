# TODO

- [x] `ToolExecuter` exec results feedback to llm
    - [x] Surface errors via `ApplicationError` + `ResultCollector.error()` + `last_error` template param
    - [x] Feedback retry loop: `Handle.handle_fine_grind` re-drafts with a deterministic results/error/source block appended to the prompt tail (prefix-cache friendly, `max_feedback_rounds` opt-in)
