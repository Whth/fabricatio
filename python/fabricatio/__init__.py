"""Fabricatio is a Python library for building llm app using event-based agent structure."""

from fabricatio._rust import TemplateManager

from fabricatio._rust_instances import template_manager
from fabricatio.config import configs
from fabricatio.core import env
from fabricatio.fs import magika
from fabricatio.journal import logger
from fabricatio.models.action import Action, WorkFlow
from fabricatio.models.events import Event
from fabricatio.models.role import Role
from fabricatio.models.task import Task
from fabricatio.models.tool import ToolBox
from fabricatio.models.utils import Message, Messages
from fabricatio.parser import Capture, CodeBlockCapture, JsonCapture, PythonCapture

__all__ = [
    "Action",
    "Capture",
    "CodeBlockCapture",
    "Event",
    "JsonCapture",
    "Message",
    "Messages",
    "PythonCapture",
    "Role",
    "Task",
    "ToolBox",
    "WorkFlow",
    "env",
    "logger",
    "magika",
    "template_manager"
]
