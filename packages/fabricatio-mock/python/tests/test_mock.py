"""Tests for the mock router module.

This module contains comprehensive tests for all mock router functions,
including testing async behavior, error handling, and edge cases.
"""

from unittest.mock import AsyncMock

import orjson
import pytest
from fabricatio_mock.models.mock_router import (
    Value,
    return_code_string,
    return_generic_string,
    return_json_obj_string,
    return_json_string,
    return_mixed_string,
    return_model_json_string,
    return_python_string,
    return_string,
)
from litellm.types.utils import ModelResponse
from pydantic import BaseModel


class TestModel(BaseModel):
    """Test model for testing purposes."""

    name: str
    age: int
    active: bool = True


kw = {"model": "openai/gpt-3.5", "messages": [{"role": "user", "content": "test"}]}


class TestReturnString:
    """Test cases for return_string function."""

    @pytest.mark.asyncio
    async def test_single_value(self) -> None:
        """Test return_string with a single value."""
        mock_router = return_string("test response")
        response = await mock_router.acompletion(**kw)

        assert isinstance(response, ModelResponse)
        assert response.choices[0].message.content == "test response"

    @pytest.mark.asyncio
    async def test_multiple_values_sequential(self) -> None:
        """Test return_string with multiple values returned sequentially."""
        mock_router = return_string("first", "second", "third")

        response1 = await mock_router.acompletion(**kw)
        response2 = await mock_router.acompletion(**kw)
        response3 = await mock_router.acompletion(**kw)
        response4 = await mock_router.acompletion(**kw)  # Should use last value

        assert response1.choices[0].message.content == "first"
        assert response2.choices[0].message.content == "second"
        assert response3.choices[0].message.content == "third"
        assert response4.choices[0].message.content == "third"  # Default to last

    @pytest.mark.asyncio
    async def test_with_default(self) -> None:
        """Test return_string with custom default value."""
        mock_router = return_string("first", "second", default="default_value")

        response1 = await mock_router.acompletion(**kw)
        response2 = await mock_router.acompletion(**kw)
        response3 = await mock_router.acompletion(**kw)  # Should use default

        assert response1.choices[0].message.content == "first"
        assert response2.choices[0].message.content == "second"
        assert response3.choices[0].message.content == "default_value"

    def test_empty_values_raises_error(self) -> None:
        """Test that return_string raises ValueError with no values."""
        with pytest.raises(ValueError, match="At least one value must be provided"):
            return_string()

    def test_returns_async_mock(self) -> None:
        """Test that return_string returns an AsyncMock instance."""
        mock_router = return_string("test")
        assert isinstance(mock_router, AsyncMock)
        assert hasattr(mock_router, "acompletion")


class TestReturnGenericString:
    """Test cases for return_generic_string function."""

    @pytest.mark.asyncio
    async def test_default_language(self) -> None:
        """Test return_generic_string with default language."""
        mock_router = return_generic_string("test content")
        response = await mock_router.acompletion(**kw)

        expected = "--- Start of string ---\ntest content\n--- End of string ---"
        assert response.choices[0].message.content == expected

    @pytest.mark.asyncio
    async def test_custom_language(self) -> None:
        """Test return_generic_string with custom language."""
        mock_router = return_generic_string("test content", lang="python")
        response = await mock_router.acompletion(**kw)

        expected = "--- Start of python ---\ntest content\n--- End of python ---"
        assert response.choices[0].message.content == expected

    @pytest.mark.asyncio
    async def test_multiple_strings(self) -> None:
        """Test return_generic_string with multiple strings."""
        mock_router = return_generic_string("first", "second", lang="test")

        response1 = await mock_router.acompletion(**kw)
        response2 = await mock_router.acompletion(**kw)

        expected1 = "--- Start of test ---\nfirst\n--- End of test ---"
        expected2 = "--- Start of test ---\nsecond\n--- End of test ---"

        assert response1.choices[0].message.content == expected1
        assert response2.choices[0].message.content == expected2

    def test_empty_strings_raises_error(self) -> None:
        """Test that return_generic_string raises ValueError with no strings."""
        with pytest.raises(ValueError, match="At least one string must be provided"):
            return_generic_string()


class TestReturnCodeString:
    """Test cases for return_code_string function."""

    @pytest.mark.asyncio
    async def test_basic_code_block(self) -> None:
        """Test return_code_string with basic code."""
        mock_router = return_code_string("print('hello')", lang="python")
        response = await mock_router.acompletion(**kw)

        expected = "```python\nprint('hello')\n```"
        assert response.choices[0].message.content == expected

    @pytest.mark.asyncio
    async def test_multiple_code_blocks(self) -> None:
        """Test return_code_string with multiple code blocks."""
        mock_router = return_code_string("code1", "code2", lang="javascript")

        response1 = await mock_router.acompletion(**kw)
        response2 = await mock_router.acompletion(**kw)

        expected1 = "```javascript\ncode1\n```"
        expected2 = "```javascript\ncode2\n```"

        assert response1.choices[0].message.content == expected1
        assert response2.choices[0].message.content == expected2

    def test_empty_codes_raises_error(self) -> None:
        """Test that return_code_string raises ValueError with no codes."""
        with pytest.raises(ValueError, match="At least one code must be provided"):
            return_code_string(lang="python")


class TestReturnPythonString:
    """Test cases for return_python_string function."""

    @pytest.mark.asyncio
    async def test_python_code_block(self) -> None:
        """Test return_python_string generates correct Python code blocks."""
        mock_router = return_python_string("def hello(): pass")
        response = await mock_router.acompletion(**kw)

        expected = "```python\ndef hello(): pass\n```"
        assert response.choices[0].message.content == expected

    @pytest.mark.asyncio
    async def test_multiple_python_blocks(self) -> None:
        """Test return_python_string with multiple Python code blocks."""
        mock_router = return_python_string("x = 1", "y = 2")

        response1 = await mock_router.acompletion(**kw)
        response2 = await mock_router.acompletion(**kw)

        assert response1.choices[0].message.content == "```python\nx = 1\n```"
        assert response2.choices[0].message.content == "```python\ny = 2\n```"


class TestReturnJsonString:
    """Test cases for return_json_string function."""

    @pytest.mark.asyncio
    async def test_json_code_block(self) -> None:
        """Test return_json_string generates correct JSON code blocks."""
        json_content = '{"key": "value"}'
        mock_router = return_json_string(json_content)
        response = await mock_router.acompletion(**kw)

        expected = f"```json\n{json_content}\n```"
        assert response.choices[0].message.content == expected

    @pytest.mark.asyncio
    async def test_multiple_json_blocks(self) -> None:
        """Test return_json_string with multiple JSON blocks."""
        mock_router = return_json_string('{"a": 1}', '{"b": 2}')

        response1 = await mock_router.acompletion(**kw)
        response2 = await mock_router.acompletion(**kw)

        assert response1.choices[0].message.content == '```json\n{"a": 1}\n```'
        assert response2.choices[0].message.content == '```json\n{"b": 2}\n```'


class TestReturnJsonObjString:
    """Test cases for return_json_obj_string function."""

    @pytest.mark.asyncio
    async def test_json_object_serialization(self) -> None:
        """Test return_json_obj_string properly serializes objects."""
        test_obj = {"name": "John", "age": 30, "active": True}
        mock_router = return_json_obj_string(test_obj)
        response = await mock_router.acompletion(**kw)

        # Check that the response contains properly formatted JSON
        content = response.choices[0].message.content
        assert content.startswith("```json\n")
        assert content.endswith("\n```")

        # Extract and verify JSON content
        json_part = content[8:-4]  # Remove ```json\n and \n```
        parsed = orjson.loads(json_part)
        assert parsed == test_obj

    @pytest.mark.asyncio
    async def test_multiple_json_objects(self) -> None:
        """Test return_json_obj_string with multiple objects."""
        obj1 = {"id": 1}
        obj2 = {"id": 2}
        mock_router = return_json_obj_string(obj1, obj2)

        response1 = await mock_router.acompletion(**kw)
        response2 = await mock_router.acompletion(**kw)

        # Verify both responses contain valid JSON
        for response, expected_obj in [(response1, obj1), (response2, obj2)]:
            content = response.choices[0].message.content
            json_part = content[8:-4]  # Remove ```json\n and \n```
            parsed = orjson.loads(json_part)
            assert parsed == expected_obj

    def test_empty_objects_raises_error(self) -> None:
        """Test that return_json_obj_string raises ValueError with no objects."""
        with pytest.raises(ValueError, match="At least one array must be provided"):
            return_json_obj_string()


class TestReturnModelJsonString:
    """Test cases for return_model_json_string function."""

    @pytest.mark.asyncio
    async def test_model_serialization(self) -> None:
        """Test return_model_json_string properly serializes Pydantic models."""
        model = TestModel(name="Alice", age=25)
        mock_router = return_model_json_string(model)
        response = await mock_router.acompletion(**kw)

        content = response.choices[0].message.content
        assert content.startswith("```json\n")
        assert content.endswith("\n```")

        # Extract and verify JSON content
        json_part = content[8:-4]
        parsed = orjson.loads(json_part)
        expected = {"name": "Alice", "age": 25, "active": True}
        assert parsed == expected

    @pytest.mark.asyncio
    async def test_multiple_models(self) -> None:
        """Test return_model_json_string with multiple models."""
        model1 = TestModel(name="Alice", age=25)
        model2 = TestModel(name="Bob", age=30, active=False)
        mock_router = return_model_json_string(model1, model2)

        response1 = await mock_router.acompletion(**kw)
        response2 = await mock_router.acompletion(**kw)

        # Verify first model
        content1 = response1.choices[0].message.content
        json_part1 = content1[8:-4]
        parsed1 = orjson.loads(json_part1)
        assert parsed1 == {"name": "Alice", "age": 25, "active": True}

        # Verify second model
        content2 = response2.choices[0].message.content
        json_part2 = content2[8:-4]
        parsed2 = orjson.loads(json_part2)
        assert parsed2 == {"name": "Bob", "age": 30, "active": False}

    def test_empty_models_raises_error(self) -> None:
        """Test that return_model_json_string raises ValueError with no models."""
        with pytest.raises(ValueError, match="At least one model must be provided"):
            return_model_json_string()


class TestValue:
    """Test cases for Value dataclass."""

    def test_model_type_conversion(self) -> None:
        """Test Value with model type."""
        model = TestModel(name="Test", age=20)
        value = Value(source=model, type="model")
        result = value.to_string()

        parsed = orjson.loads(result)
        expected = {"name": "Test", "age": 20, "active": True}
        assert parsed == expected

    def test_json_type_conversion(self) -> None:
        """Test Value with json type."""
        data = {"key": "value", "number": 42}
        value = Value(source=data, type="json")
        result = value.to_string()

        parsed = orjson.loads(result)
        assert parsed == data

    def test_python_type_conversion(self) -> None:
        """Test Value with python type."""
        code = "print('hello world')"
        value = Value(source=code, type="python")
        result = value.to_string()

        expected = "```python\nprint('hello world')\n```"
        assert result == expected

    def test_generic_type_conversion(self) -> None:
        """Test Value with generic type."""
        content = "some content"
        value = Value(source=content, type="generic")
        result = value.to_string()

        expected = "--- Start of string ---\nsome content\n--- End of string ---"
        assert result == expected

    def test_custom_convertor(self) -> None:
        """Test Value with custom convertor function."""

        def _custom_convertor(source: str) -> str:
            return f"Custom: {source}"

        value = Value(source="test", type="custom", convertor=_custom_convertor)
        result = value.to_string()

        assert result == "Custom: test"

    def test_invalid_type_raises_error(self) -> None:
        """Test Value raises ValueError for invalid type without convertor."""
        value = Value(source="test", type="invalid")

        with pytest.raises(ValueError, match="Invalid type: invalid"):
            value.to_string()


class TestReturnMixedString:
    """Test cases for return_mixed_string function."""

    @pytest.mark.asyncio
    async def test_mixed_value_types(self) -> None:
        """Test return_mixed_string with different value types."""
        model = TestModel(name="Alice", age=25)
        json_data = {"type": "json"}
        code = "x = 1"

        values = [
            Value(source=model, type="model"),
            Value(source=json_data, type="json"),
            Value(source=code, type="python"),
        ]

        mock_router = return_mixed_string(*values)

        # Test model response
        response1 = await mock_router.acompletion(**kw)
        content1 = response1.choices[0].message.content
        parsed1 = orjson.loads(content1)
        assert parsed1 == {"name": "Alice", "age": 25, "active": True}

        # Test JSON response
        response2 = await mock_router.acompletion(**kw)
        content2 = response2.choices[0].message.content
        parsed2 = orjson.loads(content2)
        assert parsed2 == {"type": "json"}

        # Test Python code response
        response3 = await mock_router.acompletion(**kw)
        content3 = response3.choices[0].message.content
        assert content3 == "```python\nx = 1\n```"

    @pytest.mark.asyncio
    async def test_mixed_with_default(self) -> None:
        """Test return_mixed_string with default value."""
        value = Value(source="test", type="generic")
        mock_router = return_mixed_string(value, default="default_response")

        response1 = await mock_router.acompletion(**kw)
        response2 = await mock_router.acompletion(**kw)  # Should use default

        expected1 = "--- Start of string ---\ntest\n--- End of string ---"
        assert response1.choices[0].message.content == expected1
        assert response2.choices[0].message.content == "default_response"

    def test_returns_router_type(self) -> None:
        """Test that return_mixed_string returns correct type."""
        value = Value(source="test", type="generic")
        result = return_mixed_string(value)

        # Should return AsyncMock (from return_string)
        assert isinstance(result, AsyncMock)


@pytest.mark.asyncio
async def test_integration_with_litellm() -> None:
    """Integration test to ensure mocks work with litellm expectations."""
    mock_router = return_string("integration test response")

    # Test with various parameters that litellm might pass
    response = await mock_router.acompletion(
        model="gpt-3.5-turbo", messages=[{"role": "user", "content": "test"}], temperature=0.7
    )

    assert isinstance(response, ModelResponse)
    assert response.choices[0].message.content == "integration test response"
    assert hasattr(response, "model")
    assert hasattr(response, "choices")


class TestAsyncBehavior:
    """Test async behavior and concurrency aspects."""

    @pytest.mark.asyncio
    async def test_concurrent_calls(self) -> None:
        """Test that concurrent calls to the same mock work correctly."""
        import asyncio

        mock_router = return_string("response1", "response2", "response3")

        # Make concurrent calls
        tasks = [mock_router.acompletion(**kw) for _ in range(3)]
        responses = await asyncio.gather(*tasks)

        # All responses should be valid ModelResponse objects
        for response in responses:
            assert isinstance(response, ModelResponse)
            assert response.choices[0].message.content in ["response1", "response2", "response3"]

    @pytest.mark.asyncio
    async def test_mock_maintains_state(self) -> None:
        """Test that mock maintains state across multiple calls."""
        mock_router = return_string("first", "second", "third")

        # Sequential calls should return values in order
        responses = []
        for _ in range(5):  # More calls than values
            response = await mock_router.acompletion(**kw)
            responses.append(response.choices[0].message.content)

        # First three should be in order, rest should be the last value
        assert responses == ["first", "second", "third", "third", "third"]
