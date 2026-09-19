"""Contract tests for the action-config injection a workflow performs before each step."""

from typing import Any, ClassVar

from fabricatio_core.models.action import Action, WorkFlow


class _Probe(Action):
    """Minimal ``ctx_override`` action: one config field beside one derived attribute."""

    ctx_override: ClassVar[bool] = True

    knob: int = 0
    """Config the task context is expected to fill."""

    @property
    def skills(self) -> list[str]:
        """Derived, read-only attribute -- the shape the novel RAG stages tripped on."""
        return ["derived"]

    async def _execute(self, **cxt: Any) -> None:
        """No-op: the injection that runs before this body is what the test exercises."""


def test_override_action_variable_fills_fields_and_leaves_derived_attributes_alone() -> None:
    """A context key that names a read-only property must not crash the injection."""
    workflow = WorkFlow(name="probe", steps=[_Probe])
    action = _Probe()

    workflow.override_action_variable(action, {"knob": 3, "skills": ["erotic-diction"]})

    assert action.knob == 3
    assert action.skills == ["derived"]
