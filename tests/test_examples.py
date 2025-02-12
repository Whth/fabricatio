import pytest

from examples.minor.hello_fabricatio import Hello
from examples.simple_chat.chat import Talk as ChatTalk
from fabricatio.models.task import Task


@pytest.fixture
def task():
    return Task(name="test task", goal="test goal", description="test description")


@pytest.fixture
def chat_talk(task):
    return ChatTalk(task_input=task)


@pytest.fixture
def hello(task):
    return Hello(task_input=task)


async def test_chat_talk_execute(chat_talk, task):
    result = await chat_talk._execute(task)
    assert result == "Hello fabricatio!"


async def test_hello_execute(hello, task):
    result = await hello._execute(task)
    assert result == "Hello fabricatio!"
