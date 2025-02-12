from fabricatio.models.events import Event

def test_event_from_string():
    event = Event.from_string("test_event: {'key': 'value'}")
    assert event.name == "test_event"
    assert event.data == {"key": "value"}

def test_event_collapse():
    event = Event(name="test_event", data={"key": "value"})
    collapsed_event = event.collapse()
    assert collapsed_event == {"name": "test_event", "data": {"key": "value"}}

def test_event_push():
    event = Event(name="test_event", data={"key": "value"})
    event.push("new_key", "new_value")
    assert event.data["new_key"] == "new_value"

def test_event_pop():
    event = Event(name="test_event", data={"key": "value"})
    popped_value = event.pop("key")
    assert popped_value == "value"
    assert "key" not in event.data

def test_event_clear():
    event = Event(name="test_event", data={"key": "value"})
    event.clear()
    assert event.data == {}