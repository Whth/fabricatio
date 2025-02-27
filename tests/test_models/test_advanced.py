# New file
from fabricatio.capabilities.task import HandleTask, ProposeTask


def test_propose_task_initialization():
    propose_task = ProposeTask(name="TestProposeTask")  # Provide a name
    assert propose_task is not None


def test_handle_task_initialization():
    handle_task = HandleTask(name="TestHandleTask")  # Provide a name
    assert handle_task is not None


def test_propose_task_methods():
    propose_task = ProposeTask(name="TestProposeTask")
    # Add assertions based on expected behavior


def test_handle_task_methods():
    handle_task = HandleTask(name="TestHandleTask")
    # Add assertions based on expected behavior
