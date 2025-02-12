import pytest

from fabricatio.models.generic import LLMUsage


@pytest.fixture
def llm_usage():
    return LLMUsage(llm_usage=True)


def test_llm_usage_initialization(llm_usage):
    assert llm_usage.llm_usage == True


def test_llm_usage_set_llm_usage(llm_usage):
    llm_usage.set_llm_usage(False)
    assert llm_usage.llm_usage == False


def test_llm_usage_get_llm_usage(llm_usage):
    assert llm_usage.get_llm_usage() == True
