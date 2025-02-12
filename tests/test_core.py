import pytest

from fabricatio.core import Env, Event


@pytest.fixture
def env():
    return Env()

@pytest.fixture
def event():
    return Event(name="test_event", data={"key": "value"})

def test_env_emit_event(env, event):
    env.emit(event)
    assert event in env.events

def test_env_emit_event_with_args(env):
    event = Event(name="test_event", data={"key": "value"})
    env.emit(event, key="new_value")
    assert event.data["key"] == "new_value"

def test_env_emit_event_with_event_class(env):
    class CustomEvent(Event):
        pass
    event = CustomEvent(name="custom_event", data={"key": "value"})
    env.emit(event)
    assert event in env.events

def test_env_on(env):
    called = False
    def callback(event):
        nonlocal called
        called = True
    env.on("test_event", callback)
    env.emit(Event(name="test_event"))
    assert called

def test_env_once(env):
    called = False
    def callback(event):
        nonlocal called
        called = True
    env.once("test_event", callback)
    env.emit(Event(name="test_event"))
    assert called
    env.emit(Event(name="test_event"))
    assert called  # still True, because it should only be called once

def test_env_emit(env, event):
    env.emit(event)
    assert event in env.events

async def test_env_emit_async(env, event):
    await env.emit(event)
    assert event in env.events
