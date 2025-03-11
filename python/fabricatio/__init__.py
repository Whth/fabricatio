"""Fabricatio is a Python library for building llm app using event-based agent structure."""

from importlib.util import find_spec

from fabricatio._rust import BibManager
from fabricatio._rust_instances import TEMPLATE_MANAGER
from fabricatio.actions.article import ExtractArticleEssence, GenerateArticleProposal, GenerateOutline
from fabricatio.actions.output import DumpFinalizedOutput
from fabricatio.core import env
from fabricatio.fs import MAGIKA, safe_json_read, safe_text_read
from fabricatio.journal import logger
from fabricatio.models.action import Action, WorkFlow
from fabricatio.models.events import Event
from fabricatio.models.extra import ArticleEssence
from fabricatio.models.role import Role
from fabricatio.models.task import Task
from fabricatio.models.tool import ToolBox
from fabricatio.models.utils import Message, Messages
from fabricatio.parser import Capture, GenericCapture, JsonCapture, PythonCapture
from fabricatio.toolboxes import arithmetic_toolbox, basic_toolboxes, fs_toolbox
from fabricatio.workflows.articles import WriteOutlineWorkFlow

__all__ = [
    "MAGIKA",
    "TEMPLATE_MANAGER",
    "Action",
    "ArticleEssence",
    "BibManager",
    "Capture",
    "DumpFinalizedOutput",
    "Event",
    "ExtractArticleEssence",
    "GenerateArticleProposal",
    "GenerateOutline",
    "GenericCapture",
    "JsonCapture",
    "Message",
    "Messages",
    "PythonCapture",
    "Role",
    "Task",
    "ToolBox",
    "WorkFlow",
    "WriteOutlineWorkFlow",
    "arithmetic_toolbox",
    "basic_toolboxes",
    "env",
    "fs_toolbox",
    "logger",
    "safe_json_read",
    "safe_text_read",
]


if find_spec("pymilvus"):
    from fabricatio.actions.rag import InjectToDB
    from fabricatio.capabilities.rag import RAG
    from fabricatio.workflows.rag import StoreArticle

    __all__ += ["RAG", "InjectToDB", "StoreArticle"]
