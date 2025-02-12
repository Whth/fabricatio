
from fabricatio.decorators import depend_on_external_cmd


def test_depend_on_external_cmd():
    def test_func():
        return "called"

    decorated_func = depend_on_external_cmd("test_bin", "Install test_bin")(test_func)

    # Mocking shutil.which to simulate the presence of the binary
    import shutil
    shutil.which = lambda x: x if x == "test_bin" else None

    assert decorated_func() == "called"

    # Mocking shutil.which to simulate the absence of the binary
    shutil.which = lambda x: None

    try:
        decorated_func()
    except RuntimeError as e:
        assert str(e) == "test_bin not found. Install test_bin"
