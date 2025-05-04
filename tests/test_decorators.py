import pytest
from fabricatio import decorators


def test_precheck_package():
    # Test that the decorator is created successfully
    @decorators.precheck_package("os", "OS package not found")
    def dummy_func():
        return True

    assert dummy_func() is True


def test_depend_on_external_cmd():
    # Test with existing command (python interpreter should be available)
    @decorators.depend_on_external_cmd("python", "Python not installed")
    def dummy_func():
        return True

    assert dummy_func() is True


def test_logging_execution_info(caplog):
    @decorators.logging_execution_info
    def dummy_func():
        return True

    result = dummy_func()
    assert result is True
    assert "Executing function: dummy_func" in caplog.text


@pytest.mark.asyncio
async def test_confirm_to_execute_yes(monkeypatch):
    monkeypatch.setattr("fabricatio.decorators.CONFIG.general.confirm_on_ops", True)
    monkeypatch.setattr(
        "questionary.confirm", lambda *args, **kwargs: type("obj", (object,), {"ask_async": lambda: True})
    )

    @decorators.confirm_to_execute
    def dummy_func():
        return True

    result = dummy_func()
    assert result is True


@pytest.mark.asyncio
async def test_confirm_to_execute_no(monkeypatch):
    monkeypatch.setattr("fabricatio.decorators.CONFIG.general.confirm_on_ops", True)
    monkeypatch.setattr(
        "questionary.confirm", lambda *args, **kwargs: type("obj", (object,), {"ask_async": lambda: False})
    )

    @decorators.confirm_to_execute
    def dummy_func():
        return True

    result = dummy_func()
    assert result is None


def test_use_temp_module():
    from importlib.util import module_from_spec, spec_from_loader

    # Create a temporary module
    spec = spec_from_loader("temp_module", loader=None)
    assert spec is not None  # Make sure spec is not None
    temp_module = module_from_spec(spec)

    # Add attribute to module
    temp_module.value = 42

    @decorators.use_temp_module(temp_module)
    def dummy_func():
        temp_module = __import__("temp_module")
        return temp_module.value

    result = dummy_func()
    assert result == 42


def test_logging_exec_time(caplog):
    @decorators.logging_exec_time
    def dummy_func():
        return True

    result = dummy_func()
    assert result is True
    assert "Execution time of dummy_func" in caplog.text
