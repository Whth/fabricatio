import pytest

from fabricatio.models.generic import LLMUsage, WithDependency


@pytest.fixture
def with_dependency_and_llm_usage():
    return WithDependency(dependencies=[]), LLMUsage(llm_usage=True)


def test_with_dependency_and_llm_usage_initialization(with_dependency_and_llm_usage):
    with_dependency, llm_usage = with_dependency_and_llm_usage
    assert with_dependency.dependencies == []
    assert llm_usage.llm_usage == True


def test_with_dependency_and_llm_usage_methods(with_dependency_and_llm_usage):
    with_dependency, llm_usage = with_dependency_and_llm_usage
    with_dependency.add_dependency("test dependency")
    llm_usage.set_llm_usage(False)
    assert "test dependency" in with_dependency.dependencies
    assert llm_usage.get_llm_usage() == False
