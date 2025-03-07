import pytest
from fabricatio.models.task import Task
from fabricatio.models.utils import TaskStatus


@pytest.fixture
def basic_task():
    return Task(name="test task", goals=["test goal"], description="test description")


@pytest.fixture
def task_with_namespace():
    return Task(name="test task", goals=["test goal"], description="test description", namespace=["test", "namespace"])


@pytest.mark.asyncio
async def test_task_status_changes(basic_task):
    await basic_task.start()
    assert basic_task._status == TaskStatus.Running

    await basic_task.finish("test output")
    assert basic_task._status == TaskStatus.Finished

    await basic_task.fail()
    assert basic_task._status == TaskStatus.Failed


@pytest.mark.asyncio
async def test_task_publishing(basic_task):
    basic_task.publish()
    assert basic_task.is_pending()


@pytest.mark.asyncio
async def test_task_output_handling(basic_task):
    await basic_task.finish("test output")
    output = await basic_task.get_output()
    assert output == "test output"


def test_task_model_post_init(task_with_namespace):
    task_with_namespace._namespace.clear()  # Clear existing segments
    task_with_namespace.model_post_init(None)
    assert task_with_namespace._namespace.segments == task_with_namespace.namespace


@pytest.mark.asyncio
async def test_task_status_progression(basic_task):
    assert basic_task._status == TaskStatus.Pending
    await basic_task.start()
    assert basic_task._status == TaskStatus.Running
    await basic_task.cancel()
    assert basic_task._status == TaskStatus.Cancelled


def test_task_with_complex_namespace():
    task = Task(name="test task", goals=["test goal"], description="test description", namespace=["a", "b", "c"])
    assert len(task.namespace) == 3
    assert task.namespace == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_task_finish_with_output(basic_task):
    output_data = {"result": "success"}
    await basic_task.finish(output_data)
    assert basic_task._status == TaskStatus.Finished
    assert await basic_task.get_output() == output_data


def test_task_event_namespacing(basic_task):
    test_status = TaskStatus.Running
    label = basic_task.status_label(test_status)
    assert all(part in label for part in [basic_task.name, test_status.value])


@pytest.mark.asyncio
async def test_task_state_transitions(basic_task):
    await basic_task.start()
    assert basic_task._status == TaskStatus.Running
    await basic_task.finish("done")
    assert basic_task._status == TaskStatus.Finished


def test_task_dependency_management():
    deps = ["dep1.py", "dep2.py"]
    task = Task(name="test", goals=["test"], description="test", dependencies=deps)
    assert task.dependencies == deps


def test_task_empty_init():
    task = Task(name="test", goals=["test"], description="test")
    assert task.namespace == []
    assert not task.dependencies


@pytest.mark.asyncio
async def test_task_cancellation_flow(basic_task):
    await basic_task.start()
    assert basic_task._status == TaskStatus.Running
    await basic_task.cancel()
    assert basic_task._status == TaskStatus.Cancelled
