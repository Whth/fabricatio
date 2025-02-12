from fabricatio.models.utils import Messages

def test_messages_add_message():
    messages = Messages()
    messages.add_message("test message")
    assert "test message" in messages.messages

def test_messages_as_list():
    messages = Messages()
    messages.add_message("test message 1")
    messages.add_message("test message 2")
    assert messages.as_list() == ["test message 1", "test message 2"]