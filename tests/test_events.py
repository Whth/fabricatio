from fabricatio.models.events import Event


def test_event_clone():
    event = Event.instantiate_from("test.event")
    cloned_event = event.clone()
    assert cloned_event.segments == ["test", "event"]
    assert cloned_event is not event  # Ensure it's a new instance


def test_event_pop():
    event = Event.instantiate_from("test.event")
    popped_segment = event.pop()
    assert popped_segment == "event"
    assert event.segments == ["test"]


def test_event_concat():
    event1 = Event.instantiate_from("test")
    event2 = Event.instantiate_from("event")
    concatenated_event = event1.concat(event2)
    assert concatenated_event.segments == ["test", "event"]


def test_event_collapse():
    event = Event.instantiate_from("test.event")
    collapsed_string = event.collapse()
    assert collapsed_string == "test.event"


def test_event_eq():
    event1 = Event.instantiate_from("test.event")
    event2 = Event.instantiate_from("test.event")
    event3 = Event.instantiate_from("another.event")
    assert event1 == event2
    assert event1 != event3
    assert event1 == "test.event"


def test_event_push():
    event = Event.instantiate_from("test")
    event.push("event")
    assert event.segments == ["test", "event"]


def test_event_clear():
    event = Event.instantiate_from("test.event")
    cleared_event = event.clear()
    assert cleared_event.segments == []
