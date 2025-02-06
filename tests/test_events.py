from fabricatio.models.events import Event


def test_event_clone():
    event = Event.from_string("test.event")
    cloned_event = event.clone()
    assert cloned_event.segments == ["test", "event"]
    assert cloned_event is not event  # Ensure it's a new instance


def test_event_pop():
    event = Event.from_string("test.event")
    popped_segment = event.pop()
    assert popped_segment == "event"
    assert event.segments == ["test"]


def test_event_concat():
    event1 = Event.from_string("test")
    event2 = Event.from_string("event")
    concatenated_event = event1.concat(event2)
    assert concatenated_event.segments == ["test", "event"]


def test_event_collapse():
    event = Event.from_string("test.event")
    collapsed_string = event.collapse()
    assert collapsed_string == "test.event"


def test_event_eq():
    event1 = Event.from_string("test.event")
    event2 = Event.from_string("test.event")
    event3 = Event.from_string("another.event")
    assert event1 == event2
    assert event1 != event3
    assert event1 == "test.event"


def test_event_push():
    event = Event.from_string("test")
    event.push("event")
    assert event.segments == ["test", "event"]


def test_event_clear():
    event = Event.from_string("test.event")
    cleared_event = event.clear()
    assert cleared_event.segments == []
