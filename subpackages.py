"""Builds and optionally publishes Python subpackages found in a directory structure.

This script automates the process of building multiple Python packages (e.g., Maturin-based
or standard Python packages) and publishing them to a package index using 'uv'.
It expects each subpackage to be in its own directory containing a 'pyproject.toml' file.
"""

import argparse
import logging
import subprocess
import tomllib  # Use tomllib for TOML parsing (Python 3.11+)
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Configuration ---
DEFAULT_ROOT_DIR = Path("packages").resolve()
DEFAULT_DIST_DIR = Path("dist").resolve()
DEFAULT_DATA_DIR = Path("extra")

# --- Logging Setup ---
# Configure logging for clear and informative output
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)


class Project:
    """Represents a single Python project to be built and/or published.

    Encapsulates project-specific metadata, build, and publish logic.
    After initialization, the `is_valid` property indicates if the project
    could be successfully parsed from its `pyproject.toml`.

    Args:
        entry_path (Path): The file system path to the project's root directory.
        dist_dir (Path): The common directory where built packages will be placed.
        pyversion (Optional[str]): The target Python version for the build, if applicable.
        dev_mode (bool): Whether to run in development mode (e.g., only 'maturin develop').

    Attributes:
        entry_path (Path): The file system path to the project's root directory.
        dist_dir (Path): The common directory where built packages will be placed.
        pyversion (Optional[str]): The target Python version for the build.
        dev_mode (bool): Whether the project is in development mode.
        name (Optional[str]): The name of the project, loaded from `pyproject.toml`.
        build_backend (Optional[str]): The build backend specified in `pyproject.toml`.
        config (Optional[Dict[str, Any]]): The parsed content of `pyproject.toml`.
    """

    def __init__(self, entry_path: Path, dist_dir: Path, pyversion: Optional[str], dev_mode: bool) -> None:
        """Initializes a Project instance."""
        self.entry_path: Path = entry_path
        self.dist_dir: Path = dist_dir
        self.pyversion: Optional[str] = pyversion
        self.dev_mode: bool = dev_mode
        self.name: Optional[str] = None
        self.build_backend: Optional[str] = None
        self.config: Optional[Dict[str, Any]] = None
        self._is_valid_project: bool = self._load_project_metadata()

    def _load_project_metadata(self) -> bool:
        """Loads and validates project metadata from its pyproject.toml file.

        Returns:
            bool: True if metadata is successfully loaded, False otherwise.
        """
        if not self.entry_path.is_dir():
            logger.warning(f"Skipping '{self.entry_path.name}': Not a directory.")
            return False

        pyproject_file = self.entry_path / "pyproject.toml"
        if not pyproject_file.is_file():
            logger.warning(f"Skipping '{self.entry_path.name}': 'pyproject.toml' not found.")
            return False

        try:
            with pyproject_file.open("rb") as f:
                config_data = tomllib.load(f)

            project_info = config_data.get("project", {})
            self.name = project_info.get("name")
            if not self.name:
                logger.error(f"Project name not found in '{pyproject_file}'. Cannot process this project.")
                return False

            build_system_info = config_data.get("build-system", {})
            self.build_backend = build_system_info.get("build-backend")
            # If build_backend is not specified, uv build usually handles it.
            # We specifically check for "maturin" due to its different command structure.

            self.config = config_data
            logger.info(
                f"Successfully loaded metadata for project: {self.name} (Entry: '{self.entry_path.name}', Backend: {self.build_backend or 'default/uv'})"
            )
            return True
        except tomllib.TOMLDecodeError as e:
            logger.error(f"Failed to parse 'pyproject.toml' in '{self.entry_path.name}': {e}")
            return False
        except Exception as e:
            logger.error(
                f"An unexpected error occurred while parsing 'pyproject.toml' in '{self.entry_path.name}': {e}"
            )
            return False

    @property
    def is_valid(self) -> bool:
        """Checks if the project metadata was loaded successfully.

        Returns:
            bool: True if the project metadata was loaded successfully, False otherwise.
        """
        return self._is_valid_project

    def _execute_subprocess(self, command: List[str], operation_description: str) -> bool:
        """Executes a subprocess command within the project's directory.

        Logs the command and its outcome.

        Args:
            command: A list of strings representing the command and its arguments.
            operation_description: A string describing the operation being performed (e.g., "build step 1/2").

        Returns:
            bool: True if the command executes successfully, False otherwise.
        """
        if not self.name:  # Should not happen if is_valid is checked
            logger.error(f"Cannot execute command for project at '{self.entry_path.name}' due to missing name.")
            return False

        logger.info(f"Running {operation_description} for '{self.name}': {' '.join(command)}")
        try:
            # Run the command from the project's directory
            process = subprocess.run(command, check=True, cwd=self.entry_path, capture_output=True, text=True, encoding="utf-8", )
            if process.stdout:
                logger.debug(f"Stdout for '{self.name}' ({operation_description}):\n{process.stdout}")
            if process.stderr:
                logger.debug(f"Stderr for '{self.name}' ({operation_description}):\n{process.stderr}")
            logger.info(f"{operation_description.capitalize()} successful for '{self.name}'.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"{operation_description.capitalize()} failed for '{self.name}'. Return code: {e.returncode}")
            if e.stdout:
                logger.error(f"Stdout:\n{e.stdout}")
            if e.stderr:
                logger.error(f"Stderr:\n{e.stderr}")
            return False
        except FileNotFoundError:
            logger.error(f"Command '{command[0]}' not found. Ensure it's installed and in your PATH.")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during {operation_description} for '{self.name}': {e}")
            return False

    def _get_build_commands(self) -> List[List[str]]:
        """Generates the list of build commands for the project.

        The commands are determined based on the project's build backend (e.g., Maturin, uv)
        and whether dev_mode is enabled.
        Assumes commands will be run with the current working directory set to the project's entry_path.

        Returns:
            List[List[str]]: A list of command lists, where each inner list represents a build command
            and its arguments. Returns an empty list if commands cannot be generated (e.g., missing
            project name or required parameters like pyversion for Maturin).
        """
        if not self.name:  # Should be caught by is_valid check before calling
            logger.error(f"Project name not available for '{self.entry_path.name}'. Cannot generate build commands.")
            return []

        resolved_dist_dir = self.dist_dir.resolve().as_posix()

        if self.build_backend == "maturin":
            if not self.pyversion:
                logger.error(f"Python version (--pyversion) is required for Maturin project '{self.name}'.")
                return []
            develop_command = [
                "uvx", "-p", self.pyversion, "--project", self.entry_path.as_posix(), "maturin", "develop", "--uv",
                "-r",

            ]

            # cargo build --workspace --bins -r -Z unstable-options --artifact-dir
            scripts_dir = self.entry_path / DEFAULT_DATA_DIR / "scripts"
            cargo_bins = [
                "cargo", "build", "-p",self.name, "--bins", "-r", "-Z", "unstable-options", "--artifact-dir",
                scripts_dir.as_posix()

            ]

            clean = [[
                "rm", (scripts_dir / "*.pdb").as_posix(), "-f"
            ], [
                "rm", (scripts_dir / "*.dwarf").as_posix(), "-f"
            ],
                ["rm", r".\packages\*\python\*\*.pyd", "-f"]
            ]

            if self.dev_mode:
                logger.info(f"Dev mode enabled for Maturin project '{self.name}'. Only running develop command.")
                return [cargo_bins, *clean, develop_command]

            build_sdist_command = [
                "uvx",
                "-p",
                self.pyversion,
                "maturin",
                "build",
                "-r",
                "--sdist",
                "-o",
                resolved_dist_dir,
            ]
            return [cargo_bins, *clean, build_sdist_command]

        # Default to 'uv build' for other backends or if backend is not 'maturin'
        # This covers standard Python packages (setuptools, hatchling, etc.)
        if self.dev_mode:
            logger.info(
                f"Dev mode enabled for non-Maturin project '{self.name}'. Build step will be skipped if publish is not enabled.")
            # For non-Maturin projects in dev mode, we might not want to build sdist/wheel
            # unless publishing is also intended. If only `build()` is called without `publish()`,
            # this could be an empty list or a specific dev install command if applicable.
            # For now, if dev_mode is on and not publishing, let's assume we don't need to build sdist/wheel.
            # The `build` method will handle this based on the commands generated.
            # If the intention of --dev is *only* to affect Maturin, this part might need adjustment.
            # For now, let's assume --dev means skip full build for all if not publishing.
            return []  # Or a specific dev install command if one exists for `uv build` equivalent.

        return [["uvx", "uv", "build", "-o", resolved_dist_dir, "--sdist", "--wheel"]]

    def build(self) -> bool:
        """Builds the project by executing its configured build commands.

        Returns:
            bool: True if all build steps are successful, False otherwise.
        """
        if not self.is_valid or not self.name:
            logger.warning(f"Skipping build for invalid or unnamed project at '{self.entry_path.name}'.")
            return False

        logger.info(f"Starting build for project: {self.name}...")
        build_commands = self._get_build_commands()

        if not build_commands:
            if self.dev_mode and self.build_backend != "maturin":
                logger.info(
                    f"Dev mode enabled for '{self.name}', and no explicit build commands for this mode (e.g. not publishing). Skipping build.")
                return True  # Considered success in dev mode if no build commands are needed
            logger.error(f"No build commands generated for '{self.name}'. Build cannot proceed.")
            return False

        for i, cmd in enumerate(build_commands):
            operation_name = f"build step {i + 1}/{len(build_commands)}"
            if not self._execute_subprocess(cmd, operation_name):
                logger.error(f"Build failed for project '{self.name}' at {operation_name}.")
                return False

        logger.info(f"Project '{self.name}' built successfully.")
        return True

    def publish(self) -> bool:
        """Publishes the built artifacts of the project.

        Searches for distributable files (.whl, .tar.gz) in the `dist_dir`
        and attempts to publish them using `uv publish`.

        Returns:
            bool: True if all found artifacts are published successfully or if no artifacts
                  are found. False if any artifact fails to publish.
        """
        if not self.is_valid or not self.name:
            logger.warning(f"Skipping publish for invalid or unnamed project at '{self.entry_path.name}'.")
            return False

        logger.info(f"Attempting to publish project: {self.name}...")

        normalized_name = self.name.replace("-", "_")
        artifacts_found = False
        all_published_successfully = True

        # Ensure dist_dir exists before globbing
        if not self.dist_dir.exists():
            logger.warning(
                f"Distribution directory '{self.dist_dir}' does not exist. Cannot find artifacts for '{self.name}'.")
            return True  # No artifacts to publish because dist_dir doesn't exist.

        for package_file in self.dist_dir.glob(f"{normalized_name}*"):
            if package_file.is_file() and package_file.suffix in (".whl", ".tar.gz"):
                artifacts_found = True
                publish_command = ["uv", "publish", package_file.resolve().as_posix()]
                if not self._execute_subprocess(publish_command, f"publishing {package_file.name}"):
                    all_published_successfully = False
                    # Continue trying to publish other artifacts even if one fails

        if not artifacts_found:
            logger.warning(
                f"No distributable artifacts (.whl, .tar.gz) found in '{self.dist_dir}' for project '{self.name}'. Nothing to publish."
            )
            return True  # Arguably, not finding artifacts isn't a "failure" of publish itself.

        if all_published_successfully:
            logger.info(f"All found artifacts for project '{self.name}' published successfully.")
        else:
            logger.error(f"Some artifacts for project '{self.name}' failed to publish.")

        return all_published_successfully


class PackageManager:
    """Manages the discovery, building, and publishing of Python projects.

    This class scans a specified root directory for subprojects,
    initializes them, and then processes each one by building and
    optionally publishing the resulting artifacts.

    Args:
        root_dir (Path): The root directory to scan for subpackage projects.
        dist_dir (Path): The common directory where built packages will be placed.
        pyversion (Optional[str]): The target Python version for builds, passed to projects.
        publish_enabled (bool): Whether to publish packages after building.
        dev_mode (bool): Whether to run in development mode.

    Attributes:
        root_dir (Path): The root directory to scan for subpackage projects.
        dist_dir (Path): The common directory where built packages will be placed.
        pyversion (Optional[str]): The target Python version for builds.
        publish_enabled (bool): Whether to publish packages after building.
        dev_mode (bool): Whether to run in development mode.
        projects (List[Project]): A list of discovered and valid `Project` instances.
    """

    def __init__(self, root_dir: Path, dist_dir: Path, pyversion: Optional[str], publish_enabled: bool,
                 dev_mode: bool) -> None:
        """Initializes the PackageManager."""
        self.root_dir: Path = root_dir
        self.dist_dir: Path = dist_dir
        self.pyversion: Optional[str] = pyversion
        self.publish_enabled: bool = publish_enabled
        self.dev_mode: bool = dev_mode
        self.projects: List[Project] = []

    def discover_projects(self) -> None:
        """Scans the root directory for project subdirectories.

        For each subdirectory found, it attempts to initialize a `Project` object.
        Valid projects (those with a parseable `pyproject.toml` and a project name)
        are added to the internal list of projects to be processed.
        """
        if not self.root_dir.is_dir():
            logger.error(f"Root directory '{self.root_dir}' not found or is not a directory. Cannot discover projects.")
            return

        logger.info(f"Scanning for projects in '{self.root_dir}'...")
        for entry in self.root_dir.iterdir():
            if entry.is_dir():  # Only consider directories as potential projects
                project = Project(entry, self.dist_dir, self.pyversion, self.dev_mode)
                if project.is_valid:
                    self.projects.append(project)
                # else: Logging about invalid project structure is handled within Project._load_project_metadata

        if not self.projects:
            logger.info("No valid projects found in the specified root directory.")
        else:
            logger.info(f"Discovered {len(self.projects)} valid project(s).")

    def process_one_project(self, project: Project) -> bool:
        """Builds and, if enabled, publishes a single project.

        Args:
            project: The project to process.

        Returns:
            bool: True if all steps (build and optional publish) were successful, False otherwise.
        """
        project_identifier = project.name or project.entry_path.name

        if not project.build():
            logger.error(f"Build failed for '{project_identifier}'. Skipping any subsequent publish step.")
            return False

        # Build was successful
        if self.publish_enabled:
            return self.handle_project_publication(project, project_identifier)
        logger.info(f"Skipping publish for '{project_identifier}' as per --no-publish flag.")
        return True  # Build successful, publish skipped as requested

    def handle_project_publication(self, project: Project, project_identifier: str) -> bool:
        """Handles the publication process for a given project.

        This includes any pre-publication steps like special builds in dev mode.

        Args:
            project: The project to publish.
            project_identifier: Identifier for logging (name or path).

        Returns:
            bool: True if publication was successful or not applicable, False on failure.
        """
        # If in dev_mode and it's a non-Maturin project, build might have been skipped by project.build().
        # We need to explicitly build sdist/wheel here before publishing.
        if self.dev_mode and project.build_backend != "maturin":
            logger.info(f"Dev mode: Explicitly building '{project_identifier}' for publishing.")
            standard_build_cmd = [
                "uvx", "uv", "build", "-o", self.dist_dir.resolve().as_posix(),
                "--sdist", "--wheel"
            ]
            # project._execute_subprocess is a method of the Project class, not one defined here.
            if not project._execute_subprocess(standard_build_cmd, "dev mode publish build"):
                logger.error(f"Failed to build '{project_identifier}' for publishing in dev mode.")
                return False

        if not project.name:  # Ensure project name is available for publishing
            logger.error(
                f"Cannot publish project from '{project.entry_path.name}' due to missing project name."
            )
            return False

        logger.info(f"Publishing is enabled for '{project.name}'.")
        return project.publish()

    @staticmethod
    def log_processing_summary(total_projects: int, success_count: int, failure_count: int) -> None:
        """Logs the summary of project processing operations."""
        logger.info("\n--- Summary ---")
        logger.info(f"Total projects processed: {total_projects}")
        logger.info(f"Successfully built/published: {success_count}")
        logger.info(f"Failed to build/publish: {failure_count}")
        logger.info("--- All projects processed. ---")

    def process_all_projects(self) -> None:
        """Processes all discovered and valid projects concurrently.

        This involves building each project and, if `publish_enabled` is True,
        attempting to publish the built artifacts. It logs a summary of
        successful and failed operations.
        """
        if not self.projects:
            logger.info("No projects to process.")
            return

        # Ensure the common distribution directory exists
        self.dist_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Using distribution directory: '{self.dist_dir.resolve()}'")

        total_projects = len(self.projects)
        success_count = 0
        failure_count = 0

        # The 'Future' type hint below assumes 'from concurrent.futures import Future'
        # The 'ThreadPoolExecutor' and 'as_completed' also from 'concurrent.futures'
        # These imports are omitted as per instruction.
        future_to_project_identifier: Dict[Future, str] = {}

        with ThreadPoolExecutor() as executor:
            logger.info(f"Submitting {total_projects} project(s) for concurrent processing...")
            for i, project_to_process in enumerate(self.projects):
                project_identifier = project_to_process.name or project_to_process.entry_path.name
                # Log the submission of the project for processing.
                # The actual start of processing for this specific project will depend on thread availability.
                logger.info(f"\n--- Submitting project {i + 1}/{total_projects}: {project_identifier} ---")

                future = executor.submit(self.process_one_project, project_to_process)
                future_to_project_identifier[future] = project_identifier

            logger.info("All projects submitted. Waiting for results...")

            processed_count = 0
            for future in as_completed(future_to_project_identifier):
                project_id_for_log = future_to_project_identifier[future]
                try:
                    # process_one_project is expected to handle its own errors and return bool
                    was_successful = future.result()
                    if was_successful:
                        success_count += 1
                        # Detailed success is logged by process_one_project or its callees
                    else:
                        failure_count += 1
                        # Detailed failure is logged by process_one_project or its callees
                except Exception as e:
                    # This case should ideally not be reached if process_one_project is robust.
                    logger.error(
                        f"Unexpected error while processing project '{project_id_for_log}': {e}",
                        exc_info=True
                    )
                    failure_count += 1
                finally:
                    processed_count += 1
                    logger.info(
                        f"Finished processing for: {project_id_for_log}. ({processed_count}/{total_projects} completed)")

        self.log_processing_summary(total_projects, success_count, failure_count)


def main() -> None:
    """Parses command-line arguments and orchestrates the package building and publishing process.

    Initializes a `PackageManager` with settings derived from command-line arguments,
    then discovers and processes all subprojects found in the specified root directory.
    """
    parser = argparse.ArgumentParser(
        description="Build and optionally publish Python subpackages located in a root directory.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--root-dir",
        type=Path,
        default=DEFAULT_ROOT_DIR,
        help="The root directory containing subpackage directories.",
    )
    parser.add_argument(
        "--dist-dir",
        type=Path,
        default=DEFAULT_DIST_DIR,
        help="The common directory to output built packages (wheels, sdist).",
    )
    parser.add_argument(
        "--no-publish",
        action="store_false",  # Sets args.publish to False if flag is present
        dest="publish",
        default=True,  # Default is to publish
        help="Disable publishing of the built packages to a package index.",
    )
    parser.add_argument(
        "--pyversion",
        type=str,
        default=None,
        help="Specify Python version (e.g., '3.12') for builders like Maturin that require it. "
             "If not provided, Maturin projects may fail to build.",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Enable development mode. For Maturin projects, this will only run 'maturin develop'. "
             "For other projects, build steps might be altered or skipped if not publishing.",
    )

    args = parser.parse_args()

    # Resolve paths to be absolute
    resolved_root_dir = args.root_dir.resolve()
    resolved_dist_dir = args.dist_dir.resolve()

    logger.info("Initializing Package Manager...")
    logger.info(f"Root directory: {resolved_root_dir}")
    logger.info(f"Distribution directory: {resolved_dist_dir}")
    logger.info(f"Python version target: {args.pyversion or 'Not specified'}")
    logger.info(f"Publishing enabled: {args.publish}")
    logger.info(f"Development mode: {args.dev}")

    manager = PackageManager(
        root_dir=resolved_root_dir,
        dist_dir=resolved_dist_dir,
        pyversion=args.pyversion,
        publish_enabled=args.publish,
        dev_mode=args.dev,
    )

    manager.discover_projects()
    manager.process_all_projects()


if __name__ == "__main__":
    main()
