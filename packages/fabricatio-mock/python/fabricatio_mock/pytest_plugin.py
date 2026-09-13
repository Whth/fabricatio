"""Pytest plugin exposing fabricatio-mock helpers as fixtures.

A suite opts into these fixtures explicitly, with ``pytest -p fabricatio_mock.pytest_plugin``
or a ``pytest_plugins`` entry in its ``conftest.py``; installing the package registers
nothing. Nothing here activates on its own: every fixture is inert until a test
requests it, and the fabricatio imports are deferred to fixture bodies so the
plugin stays cheap for unrelated suites.
"""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fabricatio_core import Role

    from fabricatio_mock.models.mock_script import MockScript


@pytest.fixture
def mock_role() -> "Callable[..., Role]":
    """Return the :func:`fabricatio_mock.utils.make_test_role` factory.

    Returns:
        Callable[..., Role]: Factory composing LLMTestRole with capability mixins.
    """
    from fabricatio_mock.utils import make_test_role

    return make_test_role


@pytest.fixture
def mock_script() -> "type[MockScript]":
    """Return the :class:`fabricatio_mock.models.mock_script.MockScript` class.

    Returns:
        type[MockScript]: The script class, used as ``with mock_script.from_texts(...)``.
    """
    from fabricatio_mock.models.mock_script import MockScript

    return MockScript


@pytest.fixture(scope="session")
def _mock_template_store(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return the session-scoped store directory behind the stub_template fixture.

    Args:
        tmp_path_factory: Pytest's session-scoped temporary directory factory.

    Returns:
        Path: A directory that outlives the individual test.
    """
    return tmp_path_factory.mktemp("fabricatio-mock-templates")


@pytest.fixture
def stub_template(_mock_template_store: Path) -> Callable[..., str]:
    """Return a factory writing stub templates into the session template store.

    Args:
        _mock_template_store: Session-scoped directory for stub templates.

    Returns:
        Callable[..., str]: ``stub_template(name, body)`` returning the template name.
    """

    def _stub_template(name: str, body: str) -> str:
        """Write one stub template.

        Args:
            name: Template name; the file is written as ``<name>.hbs``.
            body: Handlebars source of the stub.

        Returns:
            str: The template name.
        """
        from fabricatio_mock.utils import stub_template as install_stub_template

        return install_stub_template(name, body, directory=_mock_template_store)

    return _stub_template
