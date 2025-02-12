import pytest

from fabricatio.models.generic import LLMUsage, WithDependency, WithJsonExample


@pytest.fixture
def with_dependency_and_llm_usage_and_json_example():
    return WithDependency(dependencies=[]), LLMUsage(llm_usage=True), WithJsonExample(json_example={"key": "value"})


def test_with_dependency_and_llm_usage_and_json_example_initialization(with_dependency_and_llm_usage_and_json_example):
    with_dependency, llm_usage, with_json_example = with_dependency_and_llm_usage_and_json_example
    assert with_dependency.dependencies == []
    assert llm_usage.llm_usage == True
    assert with_json_example.json_example == {"key": "value"}


def test_with_dependency_and_llm_usage_and_json_example_methods(with_dependency_and_llm_usage_and_json_example):
    with_dependency, llm_usage, with_json_example = with_dependency_and_llm_usage_and_json_example
    with_dependency.add_dependency("test dependency")
    llm_usage.set_llm_usage(False)
    with_json_example.update_json_example({"new_key": "new_value"})
    assert "test dependency" in with_dependency.dependencies
    assert llm_usage.get_llm_usage() == False
    assert with_json_example.json_example == {"new_key": "new_value"}
