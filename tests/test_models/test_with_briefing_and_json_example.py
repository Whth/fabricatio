import pytest

from fabricatio.models.generic import WithBriefing, WithJsonExample


@pytest.fixture
def with_briefing_and_json_example():
    return WithBriefing(briefing="test briefing"), WithJsonExample(json_example={"key": "value"})


def test_with_briefing_and_json_example_initialization(with_briefing_and_json_example):
    with_briefing, with_json_example = with_briefing_and_json_example
    assert with_briefing.briefing == "test briefing"
    assert with_json_example.json_example == {"key": "value"}


def test_with_briefing_and_json_example_methods(with_briefing_and_json_example):
    with_briefing, with_json_example = with_briefing_and_json_example
    with_briefing.update_briefing("new briefing")
    with_json_example.update_json_example({"new_key": "new_value"})
    assert with_briefing.briefing == "new briefing"
    assert with_json_example.json_example == {"new_key": "new_value"}
