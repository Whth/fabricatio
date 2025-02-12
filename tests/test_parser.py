from fabricatio.parser import Capture


def test_capture():
    """Test the Capture class."""
    capture = Capture(pattern=r"(\d+)", target_groups=(1,))
    assert capture.capture("123") == ("123",)
    assert capture.capture("abc") is None
    assert Capture.capture_code_block("python").capture("```python\nprint('hello')\n```") == ("print('hello')",)
