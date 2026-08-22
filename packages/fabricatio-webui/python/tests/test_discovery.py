"""Tests for ecosystem-wide ``fabricatio_*`` package discovery."""

from fabricatio_webui.discovery import installed_fabricatio_packages


class TestInstalledFabricatioPackages:
    """The scanner finds every installed ecosystem package deterministically."""

    @staticmethod
    def test_pins_self_first() -> None:
        """fabricatio_webui heads the list so the demo tops the blueprint rail."""
        assert installed_fabricatio_packages()[0] == "fabricatio_webui"

    @staticmethod
    def test_covers_core_ecosystem() -> None:
        """Core, novel, and typst — all present in this repo's venv — are found."""
        found = set(installed_fabricatio_packages())
        assert {"fabricatio_core", "fabricatio_novel", "fabricatio_typst"} <= found

    @staticmethod
    def test_every_entry_is_prefixed() -> None:
        """Every returned module name carries the fabricatio_ prefix."""
        assert all(pkg.startswith("fabricatio_") for pkg in installed_fabricatio_packages())

    @staticmethod
    def test_order_is_deterministic() -> None:
        """Repeated calls return the identical ordering after the pinned head."""
        first = installed_fabricatio_packages()
        second = installed_fabricatio_packages()
        assert first == second

    @staticmethod
    def test_names_are_importable_module_stems() -> None:
        """Distribution names are normalized to importable module names."""
        import importlib

        for pkg in installed_fabricatio_packages():
            importlib.import_module(pkg)
