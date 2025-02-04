import pytest

from fabricatio.core import Env
from fabricatio.models.events import Event


@pytest.fixture
def env():
    return Env()


def test_env_on_event(env):
    @env.on("test_event")
    def handler():
        return "handled"

    assert "test_event" in env._ee._events


def test_env_emit_event(env):
    result = []

    @env.on("test_event")
    def handler():
        result.append("handled")

    env.emit("test_event")
    assert result == ["handled"]


def test_env_emit_event_with_args(env):
    result = []

    @env.on("test_event")
    def handler(arg):
        result.append(arg)

    env.emit("test_event", "test_arg")
    assert result == ["test_arg"]


def test_env_emit_event_with_event_class(env):
    result = []

    @env.on(Event.from_string("test.event"))
    def handler():
        result.append("handled")

    env.emit(Event.from_string("test.event"))
    assert result == ["handled"]
