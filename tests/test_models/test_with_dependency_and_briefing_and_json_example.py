import pytest

from fabricatio.models.generic import WithBriefing, WithDependency, WithJsonExample


@pytest.fixture
def with_dependency_and_briefing_and_json_example():
    return (
        WithDependency(dependencies=[]),
        WithBriefing(briefing="test briefing"),
        WithJsonExample(json_example={"key": "value"}),
    )


def test_with_dependency_and_briefing_and_json_example_initialization(with_dependency_and_briefing_and_json_example):
    with_dependency, with_briefing, with_json_example = with_dependency_and_briefing_and_json_example
    assert with_dependency.dependencies == []
    assert with_briefing.briefing == "test briefing"
    assert with_json_example.json_example == {"key": "value"}


def test_with_dependency_and_briefing_and_json_example_methods(with_dependency_and_briefing_and_json_example):
    with_dependency, with_briefing, with_json_example = with_dependency_and_briefing_and_json_example
    with_dependency.add_dependency("test dependency")
    with_briefing.update_briefing("new briefing")
    with_json_example.update_json_example({"new_key": "new_value"})
    assert "test dependency" in with_dependency.dependencies
    assert with_briefing.briefing == "new briefing"
    assert with_json_example.json_example == {"new_key": "new_value"}
