import pytest

from fabricatio.models.generic import LLMUsage, WithBriefing, WithDependency


@pytest.fixture
def with_dependency_and_briefing_and_llm_usage():
    return WithDependency(dependencies=[]), WithBriefing(briefing="test briefing"), LLMUsage(llm_usage=True)


def test_with_dependency_and_briefing_and_llm_usage_initialization(with_dependency_and_briefing_and_llm_usage):
    with_dependency, with_briefing, llm_usage = with_dependency_and_briefing_and_llm_usage
    assert with_dependency.dependencies == []
    assert with_briefing.briefing == "test briefing"
    assert llm_usage.llm_usage == True


def test_with_dependency_and_briefing_and_llm_usage_methods(with_dependency_and_briefing_and_llm_usage):
    with_dependency, with_briefing, llm_usage = with_dependency_and_briefing_and_llm_usage
    with_dependency.add_dependency("test dependency")
    with_briefing.update_briefing("new briefing")
    llm_usage.set_llm_usage(False)
    assert "test dependency" in with_dependency.dependencies
    assert with_briefing.briefing == "new briefing"
    assert llm_usage.get_llm_usage() == False
