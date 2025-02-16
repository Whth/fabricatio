import pytest
from fabricatio.models.task import Task

def test_task_initialization():
    task = Task(name="say hello", goal="say hello", description="say hello to the world")
    assert task.name == "say hello"
    assert task.goal == "say hello"
    assert task.description == "say hello to the world"

def test_task_methods():
    task = Task(name="say hello", goal="say hello", description="say hello to the world")
    task.start()
    assert task._status == TaskStatus.Started  # Access the private attribute directly for testing
    task.finish()
    assert task.status == "finished"
    task.cancel()
    assert task.status == "cancelled"
    task.fail()
    assert task.status == "failed"

def test_task_dependencies():
    task = Task(name="say hello", goal="say hello", description="say hello to the world")
    task.add_dependency("file1.txt")
    assert "file1.txt" in task.dependencies
    task.remove_dependency("file1.txt")
    assert "file1.txt" not in task.dependencies

# New test cases
def test_task_generate_prompt():
    task = Task(name="say hello", goal="say hello", description="say hello to the world")
    prompt = task.generate_prompt()
    # Add assertions based on expected behavior