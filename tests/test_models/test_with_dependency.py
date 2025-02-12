import pytest

from fabricatio.models.generic import WithDependency


@pytest.fixture
def with_dependency():
    return WithDependency(dependencies=[])


def test_with_dependency_add_dependency(with_dependency):
    with_dependency.add_dependency("test dependency")
    assert "test dependency" in with_dependency.dependencies


def test_with_dependency_remove_dependency(with_dependency):
    with_dependency.add_dependency("test dependency")
    with_dependency.remove_dependency("test dependency")
    assert "test dependency" not in with_dependency.dependencies
