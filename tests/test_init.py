from fabricatio import CONFIG, TEMPLATE_MANAGER, BibManager, Event


def test_config_exists():
    """Test that the CONFIG is properly imported."""
    assert CONFIG is not None


def test_template_manager_exists():
    """Test that the TEMPLATE_MANAGER is properly imported."""
    assert TEMPLATE_MANAGER is not None


def test_bib_manager_exists():
    """Test that the BibManager is properly imported."""
    assert BibManager is not None


def test_event_exists():
    """Test that the Event class is properly imported."""
    assert Event is not None


def test_event_instantiation():
    """Test basic Event instantiation and functionality."""
    # Test string event
    event1 = Event.instantiate_from("test_event")
    assert event1 is not None

    # Test list event
    event2 = Event.instantiate_from(["list", "event"])
    assert event2 is not None

    # Test event collapsing
    assert "test_event" in event1.collapse()
    assert event2.collapse() == "list.event"


def test_event_status_methods():
    """Test event status methods like push_pending, push_running, etc."""
    event = Event()

    # Test pending status
    event.push_pending()
    assert event.segments == ["pending"]

    # Test running status
    event.push_running()
    assert event.segments == ["running"]

    # Test finished status
    event.push_finished()
    assert event.segments == ["finished"]

    # Test failed status
    event.push_failed()
    assert event.segments == ["failed"]

    # Test cancelled status
    event.push_cancelled()
    assert event.segments == ["cancelled"]


def test_event_manipulation():
    """Test event manipulation methods."""
    event = Event(["seg1", "seg2"])

    # Test fork
    forked = event.fork()
    assert forked.segments == event.segments

    # Test pop
    assert event.pop() == "cancelled"  # Last status was cancelled
    assert event.pop() == "failed"
    assert event.pop() == "finished"
    assert event.pop() == "running"
    assert event.pop() == "pending"
    assert event.pop() is None  # No more segments

    # Test clear
    event.clear()
    assert event.segments == []


def test_event_concat():
    """Test event concatenation with other events."""
    base = Event(["base"])
    to_add = Event(["added"])

    base.concat(to_add)
    assert "added" in base.segments
