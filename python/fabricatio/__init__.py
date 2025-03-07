"""Fabricatio is a Python library for building llm app using event-based agent structure."""

from importlib.util import find_spec

from fabricatio._rust_instances import template_manager
from fabricatio.actions import ExtractArticleEssence
from fabricatio.core import env
from fabricatio.fs import magika
from fabricatio.journal import logger
from fabricatio.models.action import Action, WorkFlow
from fabricatio.models.events import Event
from fabricatio.models.extra import ArticleEssence
from fabricatio.models.role import Role
from fabricatio.models.task import Task
from fabricatio.models.tool import ToolBox
from fabricatio.models.utils import Message, Messages
from fabricatio.parser import Capture, CodeBlockCapture, JsonCapture, PythonCapture
from fabricatio.toolboxes import arithmetic_toolbox, basic_toolboxes, fs_toolbox, task_toolbox

__all__ = [
    "Action",
    "ArticleEssence",
    "Capture",
    "CodeBlockCapture",
    "Event",
    "ExtractArticleEssence",
    "JsonCapture",
    "Message",
    "Messages",
    "PythonCapture",
    "Role",
    "Task",
    "ToolBox",
    "WorkFlow",
    "arithmetic_toolbox",
    "basic_toolboxes",
    "env",
    "fs_toolbox",
    "logger",
    "magika",
    "task_toolbox",
    "template_manager",
]


if find_spec("pymilvus"):
    from fabricatio.capabilities.rag import RAG

    __all__ += ["RAG"]
