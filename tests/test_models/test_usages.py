import pytest
from fabricatio.models.usages import LLMUsage

def test_llmusage_initialization():
    llm_usage = LLMUsage()
    assert llm_usage is not None

def test_llmusage_achoose():
    llm_usage = LLMUsage()
    instruction = "Choose an option"
    choices = ["Option 1", "Option 2"]
    result = llm_usage.achoose(instruction, choices)
    assert result is not None

# New test cases
def test_llmusage_fallback_to():
    llm_usage = LLMUsage()
    other_llm_usage = LLMUsage()
    result = llm_usage.fallback_to(other_llm_usage)
    assert result == other_llm_usage