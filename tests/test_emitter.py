import pytest
from fabricatio import emitter


def test_env_on_with_string_event():
    called = False

    @emitter.env.on("test_event")
    def handler(value, *args, **kwargs):
        nonlocal called
        called = True

    emitter.env.emit("test_event", "value")
    assert called is True
    assert called is True


def test_env_on_with_event_object():
    called = False

    @emitter.env.on(emitter.Event(["test"]))
    def handler(*args, **kwargs):
        nonlocal called
        called = True

    emitter.env.emit(emitter.Event(["test"]))
    assert called is True


def test_env_once():
    count = 0

    @emitter.env.once("test_once")
    def handler():
        nonlocal count
        count += 1

    # Emit multiple times but should only be called once
    emitter.env.emit("test_once")
    emitter.env.emit("test_once")
    assert count == 1


@pytest.mark.asyncio
async def test_env_emit_async():
    result = None

    @emitter.env.on("test_async")
    def handler(value, *args, **kwargs):
        nonlocal result
        result = value

    await emitter.env.emit_async("test_async", "async_value")
    assert result == "async_value"


def test_event_instantiation():
    # Test string instantiation
    event1 = emitter.Event.instantiate_from("str_event")
    assert event1.segments == ["str_event"]

    # Test list instantiation
    event2 = emitter.Event.instantiate_from(["list", "event"])
    assert event2.segments == ["list", "event"]

    # Test event copy
    event3 = emitter.Event.instantiate_from(event2)
    assert event3.segments == event2.segments


def test_event_collapse():
    event = emitter.Event(["seg1", "seg2"])
    assert event.collapse() == "seg1.seg2"


def test_event_derive():
    base = emitter.Event(["base"])
    derived = base.derive(["derived"])
    assert derived.segments == ["base", "derived"]


def test_event_status_methods():
    event = emitter.Event()
    assert event.segments == []

    # Test status methods
    event.push_pending()
    assert event.segments == ["pending"]

    event.push_running()
    assert event.segments == ["running"]

    event.push_finished()
    assert event.segments == ["finished"]

    event.push_failed()
    assert event.segments == ["failed"]

    event.push_cancelled()
    assert event.segments == ["cancelled"]


def test_event_pop():
    event = emitter.Event(["seg1", "seg2", "seg3"])
    assert event.pop() == "seg3"
    assert event.pop() == "seg2"
    assert event.pop() == "seg1"
    assert event.pop() is None


def test_event_clear():
    event = emitter.Event(["seg1", "seg2"])
    event.clear()
    assert event.segments == []


def test_event_equality():
    event1 = emitter.Event(["seg1", "seg2"])
    event2 = emitter.Event(["seg1", "seg2"])
    event3 = emitter.Event(["seg1", "seg3"])

    assert event1 == event2
    assert event1 != event3
    assert event1 != "not_an_event"
