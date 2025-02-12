import pytest

from fabricatio.models.generic import LLMUsage, WithBriefing


@pytest.fixture
def with_briefing_and_llm_usage():
    return WithBriefing(briefing="test briefing"), LLMUsage(llm_usage=True)


def test_with_briefing_and_llm_usage_initialization(with_briefing_and_llm_usage):
    with_briefing, llm_usage = with_briefing_and_llm_usage
    assert with_briefing.briefing == "test briefing"
    assert llm_usage.llm_usage == True


def test_with_briefing_and_llm_usage_methods(with_briefing_and_llm_usage):
    with_briefing, llm_usage = with_briefing_and_llm_usage
    with_briefing.update_briefing("new briefing")
    llm_usage.set_llm_usage(False)
    assert with_briefing.briefing == "new briefing"
    assert llm_usage.get_llm_usage() == False
