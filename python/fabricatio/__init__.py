"""Fabricatio is a Python library for building llm app using event-based agent structure."""

from importlib.util import find_spec

from fabricatio import actions, toolboxes, workflows
from fabricatio._rust import BibManager
from fabricatio._rust_instances import TEMPLATE_MANAGER
from fabricatio.core import env
from fabricatio.journal import logger
from fabricatio.models import extra
from fabricatio.models.action import Action, WorkFlow
from fabricatio.models.events import Event
from fabricatio.models.role import Role
from fabricatio.models.task import Task
from fabricatio.models.tool import ToolBox
from fabricatio.parser import Capture, GenericCapture, JsonCapture, PythonCapture

__all__ = [
    "TEMPLATE_MANAGER",
    "Action",
    "BibManager",
    "Capture",
    "Event",
    "GenericCapture",
    "JsonCapture",
    "PythonCapture",
    "Role",
    "Task",
    "ToolBox",
    "WorkFlow",
    "actions",
    "env",
    "extra",
    "logger",
    "toolboxes",
    "workflows",
]


if find_spec("pymilvus"):
    from fabricatio.capabilities.rag import RAG

    __all__ += ["RAG"]
