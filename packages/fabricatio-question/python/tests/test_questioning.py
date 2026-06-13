"""Tests for fabricatio-question."""

from unittest.mock import AsyncMock, patch

import pytest
from fabricatio_question.config import QuestionConfig, question_config
from fabricatio_question.models.questions import SelectionQuestion

# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestQuestionConfig:
    """Tests for QuestionConfig."""

    def test_default_selection_template(self) -> None:
        """Test default selection_template value."""
        cfg = QuestionConfig()
        assert cfg.selection_template == "built-in/selection"

    def test_default_selection_display_template(self) -> None:
        """Test default selection_display_template value."""
        cfg = QuestionConfig()
        assert cfg.selection_display_template == "built-in/selection_display"

    def test_custom_config(self) -> None:
        """Test creating config with custom values."""
        cfg = QuestionConfig(selection_template="custom/sel", selection_display_template="custom/disp")
        assert cfg.selection_template == "custom/sel"
        assert cfg.selection_display_template == "custom/disp"

    def test_config_is_frozen(self) -> None:
        """Test that QuestionConfig is frozen."""
        cfg = QuestionConfig()
        with pytest.raises(AttributeError):
            cfg.selection_template = "new"  # type: ignore[misc]

    def test_question_config_singleton(self) -> None:
        """Test that question_config is a QuestionConfig instance."""
        assert isinstance(question_config, QuestionConfig)


# ---------------------------------------------------------------------------
# SelectionQuestion model tests
# ---------------------------------------------------------------------------


class TestSelectionQuestion:
    """Tests for SelectionQuestion model."""

    def test_model_creation(self) -> None:
        """Test creating a SelectionQuestion."""
        q = SelectionQuestion(q="Pick one", option=["a", "b", "c"])
        assert q.q == "Pick one"
        assert q.option == ["a", "b", "c"]

    def test_model_fields(self) -> None:
        """Test that model has correct fields."""
        fields = SelectionQuestion.model_fields
        assert "q" in fields
        assert "option" in fields

    @pytest.mark.asyncio
    async def test_single_calls_questionary(self) -> None:
        """Test that single() delegates to questionary.select."""
        q = SelectionQuestion(q="Choose", option=["x", "y"])

        mock_prompt = AsyncMock()
        mock_prompt.ask_async = AsyncMock(return_value="x")

        with patch("questionary.select", return_value=mock_prompt) as mock_select:
            result = await q.single()
            mock_select.assert_called_once_with("Choose", choices=["x", "y"])
            assert result == "x"

    @pytest.mark.asyncio
    async def test_multiple_no_k(self) -> None:
        """Test that multiple() with k=0 uses questionary.checkbox without validation."""
        q = SelectionQuestion(q="Choose many", option=["a", "b", "c"])

        mock_prompt = AsyncMock()
        mock_prompt.ask_async = AsyncMock(return_value=["a", "c"])

        with patch("questionary.checkbox", return_value=mock_prompt) as mock_checkbox:
            result = await q.multiple(k=0)
            mock_checkbox.assert_called_once()
            call_kwargs = mock_checkbox.call_args
            assert call_kwargs[1]["choices"] == ["a", "b", "c"]
            assert result == ["a", "c"]

    @pytest.mark.asyncio
    async def test_multiple_with_k(self) -> None:
        """Test that multiple() with k>0 passes a validator."""
        q = SelectionQuestion(q="Pick 2", option=["a", "b", "c"])

        mock_prompt = AsyncMock()
        mock_prompt.ask_async = AsyncMock(return_value=["a", "b"])

        with patch("questionary.checkbox", return_value=mock_prompt) as mock_checkbox:
            result = await q.multiple(k=2)
            mock_checkbox.assert_called_once()
            call_kwargs = mock_checkbox.call_args
            assert call_kwargs[1]["choices"] == ["a", "b", "c"]
            # The validator should be present
            assert "validate" in call_kwargs[1]
            validator = call_kwargs[1]["validate"]
            assert validator(["a", "b"]) is True
            assert validator(["a"]) != True
            assert result == ["a", "b"]
