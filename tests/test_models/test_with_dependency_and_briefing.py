import pytest

from fabricatio.models.generic import WithBriefing, WithDependency


@pytest.fixture
def with_dependency_and_briefing():
    return WithDependency(dependencies=[]), WithBriefing(briefing="test briefing")


def test_with_dependency_and_briefing_initialization(with_dependency_and_briefing):
    with_dependency, with_briefing = with_dependency_and_briefing
    assert with_dependency.dependencies == []
    assert with_briefing.briefing == "test briefing"


def test_with_dependency_and_briefing_methods(with_dependency_and_briefing):
    with_dependency, with_briefing = with_dependency_and_briefing
    with_dependency.add_dependency("test dependency")
    with_briefing.update_briefing("new briefing")
    assert "test dependency" in with_dependency.dependencies
    assert with_briefing.briefing == "new briefing"
