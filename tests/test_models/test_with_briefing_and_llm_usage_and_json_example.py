import pytest

from fabricatio.models.generic import LLMUsage, WithBriefing, WithJsonExample


@pytest.fixture
def with_briefing_and_llm_usage_and_json_example():
    return (
        WithBriefing(briefing="test briefing"),
        LLMUsage(llm_usage=True),
        WithJsonExample(json_example={"key": "value"}),
    )


def test_with_briefing_and_llm_usage_and_json_example_initialization(with_briefing_and_llm_usage_and_json_example):
    with_briefing, llm_usage, with_json_example = with_briefing_and_llm_usage_and_json_example
    assert with_briefing.briefing == "test briefing"
    assert llm_usage.llm_usage == True
    assert with_json_example.json_example == {"key": "value"}


def test_with_briefing_and_llm_usage_and_json_example_methods(with_briefing_and_llm_usage_and_json_example):
    with_briefing, llm_usage, with_json_example = with_briefing_and_llm_usage_and_json_example
    with_briefing.update_briefing("new briefing")
    llm_usage.set_llm_usage(False)
    with_json_example.update_json_example({"new_key": "new_value"})
    assert with_briefing.briefing == "new briefing"
    assert llm_usage.get_llm_usage() == False
    assert with_json_example.json_example == {"new_key": "new_value"}
