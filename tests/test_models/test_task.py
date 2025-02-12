import pytest
from fabricatio.models.task import Task

@pytest.fixture
def task():
    return Task(name="test task", goal="test goal", description="test description")

def test_task_initialization(task):
    assert task.name == "test task"
    assert task.goal == "test goal"
    assert task.description == "test description"

def test_task_start(task):
    task.start()
    assert task.status == "started"

def test_task_finish(task):
    task.finish()
    assert task.status == "finished"

def test_task_cancel(task):
    task.cancel()
    assert task.status == "cancelled"

def test_task_fail(task):
    task.fail("test error")
    assert task.status == "failed"
    assert task.error == "test error"

def test_task_output(task):
    task.output = "test output"
    assert task.output == "test output"

def test_task_dependency(task):
    task.add_dependency("test dependency")
    assert "test dependency" in task.dependencies

def test_task_json_example(task):
    task.json_example = {"key": "value"}
    assert task.json_example == {"key": "value"}