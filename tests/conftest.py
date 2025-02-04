import pytest

from fabricatio.config import Settings


@pytest.fixture
def settings():
    return Settings()
