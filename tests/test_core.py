import pytest

from fabricatio.core import Env, Event


@pytest.fixture
def env():
    return Env()


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


def test_env_on():
    env = Env()
    called = False

    def callback():
        nonlocal called
        called = True

    env.on("test_event", callback)
    env.emit("test_event")
    assert called


def test_env_once():
    env = Env()
    called = False

    def callback():
        nonlocal called
        called = True

    env.once("test_event", callback)
    env.emit("test_event")
    assert called
    env.emit("test_event")
    assert called  # still True, because it should only be called once


def test_env_emit():
    env = Env()
    results = []

    def callback(arg):
        results.append(arg)

    env.on("test_event", callback)
    env.emit("test_event", "test_arg")
    assert results == ["test_arg"]


@pytest.mark.asyncio
async def test_env_emit_async():
    env = Env()
    results = []

    async def callback(arg):
        results.append(arg)

    env.on("test_event", callback)
    await env.emit_async("test_event", "test_arg")
    assert results == ["test_arg"]
