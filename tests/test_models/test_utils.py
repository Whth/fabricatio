from fabricatio.models.utils import Messages


def test_messages_add_message():
    messages = Messages()
    messages.add_message("user", "Hello")
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "Hello"


def test_messages_as_list():
    messages = Messages()
    messages.add_message("user", "Hello")
    messages.add_message("system", "Hi")
    assert messages.as_list() == [
        {"role": "user", "content": "Hello"},
        {"role": "system", "content": "Hi"},
    ]
