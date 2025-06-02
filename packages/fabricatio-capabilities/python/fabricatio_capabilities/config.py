"""Module containing configuration classes for fabricatio-capabilities."""

from dataclasses import dataclass

from fabricatio_core import CONFIG


@dataclass
class CapabilitiesConfig:
    """Configuration for fabricatio-capabilities."""

    extract_template: str = "extract"
    """The name of the extract template which will be used to extract model from string."""
    # Code Generation Templates

    draft_tool_usage_code_template: str = "draft_tool_usage_code"
    """The name of the draft tool usage code template which will be used to draft tool usage code."""
    dispatch_task_template: str = "dispatch_task"
    """The name of the dispatch task template which will be used to dispatch a task."""

    # Rating and Evaluation Templates
    rate_fine_grind_template: str = "rate_fine_grind"
    """The name of the rate fine grind template which will be used to rate fine grind."""

    draft_rating_manual_template: str = "draft_rating_manual"
    """The name of the draft rating manual template which will be used to draft rating manual."""

    draft_rating_criteria_template: str = "draft_rating_criteria"
    """The name of the draft rating criteria template which will be used to draft rating criteria."""

    extract_reasons_from_examples_template: str = "extract_reasons_from_examples"
    """The name of the extract reasons from examples template which will be used to extract reasons from examples."""

    extract_criteria_from_reasons_template: str = "extract_criteria_from_reasons"
    """The name of the extract criteria from reasons template which will be used to extract criteria from reasons."""

    draft_rating_weights_klee_template: str = "draft_rating_weights_klee"
    """The name of the draft rating weights klee template which will be used to draft rating weights with Klee method."""


capabilities_config = CONFIG.load("capabilities", CapabilitiesConfig)
__all__ = ["capabilities_config"]
