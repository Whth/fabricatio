import pytest

from fabricatio.models.generic import WithBriefing


@pytest.fixture
def with_briefing():
    return WithBriefing(briefing="test briefing")


def test_with_briefing_initialization(with_briefing):
    assert with_briefing.briefing == "test briefing"


def test_with_briefing_update_briefing(with_briefing):
    with_briefing.update_briefing("new briefing")
    assert with_briefing.briefing == "new briefing"
