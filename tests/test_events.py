from fabricatio.models.events import Event


def test_event_clone():
    event = Event(name="test_event", data={"key": "value"})
    cloned_event = event.clone()
    assert cloned_event != event
    assert cloned_event.name == event.name
    assert cloned_event.data == event.data

def test_event_pop():
    event = Event(name="test_event", data={"key": "value"})
    popped_value = event.pop("key")
    assert popped_value == "value"
    assert "key" not in event.data

def test_event_concat():
    event1 = Event(name="test_event1", data={"key1": "value1"})
    event2 = Event(name="test_event2", data={"key2": "value2"})
    concatenated_event = event1.concat(event2)
    assert concatenated_event.data == {"key1": "value1", "key2": "value2"}

def test_event_collapse():
    event = Event(name="test_event", data={"key": "value"})
    collapsed_event = event.collapse()
    assert collapsed_event == {"name": "test_event", "data": {"key": "value"}}

def test_event_eq():
    event1 = Event(name="test_event", data={"key": "value"})
    event2 = Event(name="test_event", data={"key": "value"})
    assert event1 == event2

def test_event_push():
    event = Event(name="test_event", data={"key": "value"})
    event.push("new_key", "new_value")
    assert event.data["new_key"] == "new_value"

def test_event_clear():
    event = Event(name="test_event", data={"key": "value"})
    event.clear()
    assert event.data == {}
