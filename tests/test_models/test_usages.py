from unittest.mock import AsyncMock

import pytest
from fabricatio.models.task import Task
from fabricatio.models.tool import Tool, ToolBox
from fabricatio.models.usages import LLMUsage, ToolBoxUsage
from litellm.types.utils import ModelResponse
from pydantic import HttpUrl, SecretStr


@pytest.fixture
def basic_llm_usage():
    return LLMUsage(
        llm_model="gpt-4",
        llm_temperature=0.7,
        llm_api_key=SecretStr("test-key"),
        llm_api_endpoint=HttpUrl("https://api.example.com"),
    )


@pytest.fixture
def mock_task():
    return Task(name="test_task", goals=["test goal"], description="test description")


@pytest.fixture
def mock_toolbox():
    return ToolBox(
        name="test_toolbox",
        tools=[
            Tool(name="tool1", description="Test tool 1", source=lambda x: x),
            Tool(name="tool2", description="Test tool 2", source=lambda x: x),
        ],
    )


# LLMUsage Tests
def test_llmusage_initialization():
    llm_usage = LLMUsage()
    assert llm_usage is not None
    assert llm_usage.llm_model is None
    assert llm_usage.llm_temperature is None


def test_llmusage_with_parameters(basic_llm_usage):
    assert basic_llm_usage.llm_model == "gpt-4"
    assert basic_llm_usage.llm_temperature == 0.7
    assert basic_llm_usage.llm_api_key.get_secret_value() == "test-key"


def test_llmusage_fallback_to():
    base = LLMUsage(llm_model="model-a")
    other = LLMUsage(llm_temperature=0.8, llm_max_tokens=100)
    result = base.fallback_to(other)
    assert result.llm_model == "model-a"
    assert result.llm_temperature == 0.8
    assert result.llm_max_tokens == 100


def test_llmusage_hold_to():
    base = LLMUsage(llm_model="model-a", llm_temperature=0.7)
    other = LLMUsage()
    base.hold_to([other])  # Pass as list
    assert other.llm_model == "model-a"
    assert other.llm_temperature == 0.7


@pytest.mark.asyncio
async def test_llmusage_aquery(basic_llm_usage, monkeypatch):
    mock_response = ModelResponse(choices=[])
    mock_completion = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("litellm.acompletion", mock_completion)

    result = await basic_llm_usage.aquery([{"role": "user", "content": "test"}])
    assert result == mock_response


@pytest.mark.asyncio
async def test_llmusage_aask(basic_llm_usage, monkeypatch):
    from litellm import mock_completion

    async def mock_comp(*args, **kwargs):
        return mock_completion(*args, **kwargs)

    monkeypatch.setattr("litellm.acompletion", mock_comp)

    result = await basic_llm_usage.aask("test question")
    assert result == "This is a mock request"


@pytest.mark.asyncio
async def test_llmusage_aask_validate(basic_llm_usage, monkeypatch):
    # Mock the aask method directly
    async def mock_aask(*args, **kwargs):
        return "42"

    monkeypatch.setattr(LLMUsage, "aask", AsyncMock(side_effect=mock_aask))
    result = await basic_llm_usage.aask_validate("test", validator=lambda x: int(x) if x.isdigit() else None)
    assert result == 42


@pytest.mark.asyncio
async def test_llmusage_ajudge(basic_llm_usage, monkeypatch):
    # Mock the aask_validate method directly
    async def mock_aask_validate(*args, **kwargs):
        return True

    monkeypatch.setattr(LLMUsage, "aask_validate", AsyncMock(side_effect=mock_aask_validate))
    result = await basic_llm_usage.ajudge("test prompt")
    assert result is True


@pytest.mark.asyncio
async def test_llmusage_aask_validate_failure(basic_llm_usage, monkeypatch):
    # Mock the aask method directly
    async def mock_aask(*args, **kwargs):
        return "invalid"

    monkeypatch.setattr(LLMUsage, "aask", AsyncMock(side_effect=mock_aask))
    with pytest.raises(ValueError):
        await basic_llm_usage.aask_validate("test", validator=lambda x: int(x) if x.isdigit() else None)


# ToolBoxUsage Tests


def test_toolboxusage_initialization():
    usage = ToolBoxUsage()
    assert usage is not None
    assert len(usage.toolboxes) == 0


def test_toolboxusage_available_toolbox_names(mock_toolbox):
    usage = ToolBoxUsage(toolboxes={mock_toolbox})
    assert len(usage.available_toolbox_names) == 1
    assert usage.available_toolbox_names[0] == "test_toolbox"


@pytest.mark.asyncio
async def test_toolboxusage_choose_tools_empty(mock_task):
    usage = ToolBoxUsage()
    empty_toolbox = ToolBox(name="empty", tools=[])  # Create new toolbox with empty tools
    result = await usage.choose_tools(mock_task, empty_toolbox)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_toolboxusage_choose_tools_empty(mock_task, mock_toolbox):
    usage = ToolBoxUsage()
    mock_toolbox.tools.clear()
    result = await usage.choose_tools(mock_task, mock_toolbox)
    assert len(result) == 0


def test_toolboxusage_supply_tools_from(mock_toolbox):
    usage1 = ToolBoxUsage(toolboxes={mock_toolbox})
    usage2 = ToolBoxUsage()
    usage2.supply_tools_from(usage1)
    assert len(usage2.toolboxes) == 1


def test_toolboxusage_provide_tools_to(mock_toolbox):
    usage1 = ToolBoxUsage(toolboxes={mock_toolbox})
    usage2 = ToolBoxUsage()
    usage1.provide_tools_to(usage2)
    assert len(usage2.toolboxes) == 1


@pytest.mark.asyncio
async def test_toolboxusage_gather_tools(mock_task, mock_toolbox, monkeypatch):
    usage = ToolBoxUsage(toolboxes={mock_toolbox})

    async def mock_gather_fine(*args, **kwargs):
        return list(mock_toolbox.tools)

    monkeypatch.setattr(ToolBoxUsage, "gather_tools_fine_grind", mock_gather_fine)

    result = await usage.gather_tools(mock_task)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_llmusage_aask_validate_failure(basic_llm_usage, monkeypatch):
    from litellm import mock_completion

    async def mock_comp(*args, **kwargs):
        return mock_completion(*args, **kwargs)

    monkeypatch.setattr("litellm.acompletion", mock_comp)
    assert await basic_llm_usage.aask_validate("test", validator=lambda x: None) is None
    assert await basic_llm_usage.aask_validate("test", validator=lambda x: None, default="fallback") == "fallback"


def test_toolboxusage_inheritance():
    usage = ToolBoxUsage()
    assert isinstance(usage, LLMUsage)
    assert hasattr(usage, "llm_model")
    assert hasattr(usage, "toolboxes")
