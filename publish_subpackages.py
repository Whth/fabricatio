import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

ROOT_DIR = Path("packages").resolve()  # Default root directory
DIST = Path("dist").resolve()


def get_root_dir() -> Path:
    """Gets the root directory from command line arguments or uses the default."""
    return Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT_DIR


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
        return ["uvx", "--project", project_name, "--directory", entry.as_posix(), "maturin", "build", "-r",
                "--sdist", "-o", DIST.as_posix()]
    else:
        # uvx --project fabricatio-judge --directory .\packages\fabricatio-judge\ uv build
        return ["uvx", "--project", project_name, "--directory", entry.as_posix(), "uv",
                "build"]  # Assuming uv publish expects the path to the package dir


def run_build_command(command: List[str], project_name: str, entry: Path, build_backend: str) -> None:
    """Runs the build command."""
    print(f"🚀 Running command: {' '.join(str(c) for c in command)}")
    try:
        subprocess.run(command, check=True, cwd=entry if build_backend != "maturin" else None)
        print(f"✅ Successfully built {project_name}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed for {project_name}: {e}")
    except FileNotFoundError:
        print(f"❌ Command '{command[0]}' not found. Make sure it's installed and in your PATH.")


def process_project(entry: Path) -> None:
    """Processes a single project directory."""
    if not entry.is_dir():
        return

    pyproject_path = entry / "pyproject.toml"
    if not pyproject_path.is_file():
        return

    print(f"\n🔍 Checking project: {entry.name}")

    parsed_info = parse_pyproject(pyproject_path)
    if not parsed_info:
        return

    build_backend, project_name, _ = parsed_info
    print(f"📦 Project: {project_name}, Build backend: {build_backend}")

    command = build_command(project_name, entry, build_backend)
    run_build_command(command, project_name, entry, build_backend)


def main():
    root_dir = get_root_dir()
    DIST.mkdir(parents=True, exist_ok=True)

    for entry in root_dir.iterdir():
        process_project(entry)


if __name__ == "__main__":
    main()
