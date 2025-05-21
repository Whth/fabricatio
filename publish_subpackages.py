import argparse
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path("packages").resolve()  # Default root directory
DIST = Path("dist").resolve()


def parse_pyproject(pyproject_path: Path) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    """Parses the pyproject.toml file and returns build backend and project name."""
    try:
        with pyproject_path.open("rb") as f:
            config = tomllib.load(f)
            build_system = config.get("build-system", {})
            build_backend = build_system.get("build-backend", "")
            project_name = config.get("project", {}).get("name")
            if not project_name:
                print(f"⚠️ Project name not found in {pyproject_path.parent.name}")
                return None
            return build_backend, project_name, config
    except Exception as e:
        print(f"⚠️ Failed to parse pyproject.toml in {pyproject_path.parent.name}: {e}")
        return None


def build_command(project_name: str, entry: Path, build_backend: str) -> List[str]:
    """Builds the command list based on the build backend."""
    if build_backend == "maturin":
        # The following line was present in the original code but is not valid Python.
        # It appears to be a comment or a command meant for manual execution for a specific package.
        # uvx --directory .\packages\fabricatio-core\ maturin publish --skip-existing
        return [
            [
                "uvx",
                "--project",
                project_name,
                "--directory",
                entry.as_posix(),
                "maturin",
                "develop",
                "--uv",
                "-r",
            ],
            [
                "uvx",
                "--project",
                project_name,
                "--directory",
                entry.as_posix(),
                "maturin",
                "build",
                "-r",
                "--sdist",
                "-o",
                DIST.as_posix(),
            ],
        ]
    # uvx --project fabricatio-judge --directory .\packages\fabricatio-judge\ uv build
    return [
        ["uvx", "--project", project_name, "--directory", entry.as_posix(), "uv", "build"]
    ]  # Assuming uv publish expects the path to the package dir


def run_build_command(command: List[List[str]], project_name: str, entry: Path, build_backend: str) -> None:
    """Runs the build command."""
    for c in command:
        print(f"🚀 Running command: {' '.join(c)}")
        try:
            subprocess.run(c, check=True)
            print(f"✅ Successfully built {project_name}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Build failed for {project_name}: {e}")
        except FileNotFoundError:
            print(f"❌ Command '{c[0]}' not found. Make sure it's installed and in your PATH.")


def _validate_project_entry(entry: Path) -> Optional[Path]:
    """Validates if the entry is a directory and contains pyproject.toml."""
    if not entry.is_dir():
        return None
    pyproject_path = entry / "pyproject.toml"
    if not pyproject_path.is_file():
        return None
    return pyproject_path


def _build_project(project_name: str, entry: Path, build_backend: str) -> None:
    """Builds the specified project."""
    command = build_command(project_name, entry, build_backend)
    run_build_command(command, project_name, entry, build_backend)


def _publish_project(project_name: str) -> None:
    """Publishes the built packages for the project."""
    for package_file in DIST.glob(f"{project_name.replace('-', '_')}*.*"):
        if package_file.suffix in (".whl", ".tar.gz"):
            publish_command = ["uv", "publish", package_file.as_posix()]
            print(f"🚀 Publishing: {' '.join(publish_command)}")
            try:
                subprocess.run(publish_command, check=True)
                print(f"✅ Successfully published {package_file.name}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to publish {package_file.name}: {e}")
            except FileNotFoundError:
                print("❌ Command 'uv' not found. Make sure it's installed and in your PATH.")


def process_project(entry: Path, publish_enabled: bool) -> None:
    """Processes a single project directory: validates, builds, and optionally publishes it."""
    pyproject_path = _validate_project_entry(entry)
    if not pyproject_path:
        return

    print(f"\n🔍 Checking project: {entry.name}")

    parsed_info = parse_pyproject(pyproject_path)
    if not parsed_info:
        return

    build_backend, project_name, _ = parsed_info
    print(f"📦 Project: {project_name}, Build backend: {build_backend}")

    _build_project(project_name, entry, build_backend)

    if publish_enabled:
        _publish_project(project_name)
    else:
        print(f"📦 Skipping publish for {project_name} as per configuration.")


def main():
    parser = argparse.ArgumentParser(description="Build and optionally publish Python subpackages.")
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=ROOT_DIR,
        help="The root directory containing the subpackages.",
    )
    parser.add_argument(
        "--no-publish",
        action="store_false",
        dest="publish",
        help="Disable publishing of the built packages.",
    )
    parser.set_defaults(publish=True)

    args = parser.parse_args()

    root_dir = args.root_dir.resolve()
    publish_enabled = args.publish

    DIST.mkdir(parents=True, exist_ok=True)

    if not root_dir.is_dir():
        print(f"❌ Root directory '{root_dir}' not found.")
        return

    for entry in root_dir.iterdir():
        process_project(entry, publish_enabled)


if __name__ == "__main__":
    main()
