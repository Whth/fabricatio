"""Build packages with customizable Python version."""

import argparse
import logging
import subprocess
import tomllib
from concurrent.futures.process import ProcessPoolExecutor
from pathlib import Path
from typing import List, Union

PACKAGES_DIR = (Path.cwd() / "packages").absolute()
DIST = (Path.cwd() / "dist").absolute()
SCRIPTS_DIR = Path("extra") / "scripts"

PYTHON_VERSION = "3.13"

POOL = ProcessPoolExecutor()


def run_cmd(cmd_sequence: List[List[str]], desc: str) -> bool:
    """Run a sequence of shell commands and log output.

    Args:
        cmd_sequence: A list of command sequences to execute.
        desc: Description of the command being executed for logging.

    Returns:
        True if all commands succeed, False otherwise.
    """
    try:
        for cmd in cmd_sequence:
            logging.info(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)  # noqa: S603
            logging.debug(f"Command output: {result.stdout}")
        logging.info(f"{desc} completed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error occurred during '{desc}': {e.stderr}")
        return False


def is_using_maturin(project_root: Union[str, Path]) -> bool:
    """Check if pyproject.toml in the specified project root uses maturin as build-backend.

    Returns:
        - True: if maturin is used
        - False: if not used or error occurs
    """
    project_root = Path(project_root)
    pyproject_path = project_root / "pyproject.toml"

    if not pyproject_path.is_file():
        return False

    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        build_backend = data.get("build-system", {}).get("build-backend")
        return build_backend == "maturin"
    except tomllib.TOMLDecodeError:
        return False


def make_maturin_dev(project_root: Union[str, Path]) -> bool:
    """Build the Rust project using maturin in development mode.

    Args:
        project_root: The root directory of the project.

    Returns:
        True if the operation succeeds, False otherwise.
    """
    project_root = Path(project_root)

    return run_cmd(
        [["uvx", "--directory", project_root.as_posix(), "maturin", "develop", "-r", "--uv"]],
        f"maturin develop mode for {project_root.name}",
    )


def make_all_bins(project_root: Union[str, Path]) -> bool:
    """Build all binaries using Cargo and clean up debug files.

    Args:
        project_root: The root directory of the project.

    Returns:
        True if the operation succeeds, False otherwise.
    """
    project_root = Path(project_root)

    scripts_dir = project_root.joinpath(SCRIPTS_DIR)
    for f in [*list(scripts_dir.rglob("*.pyd")), *list(scripts_dir.rglob("*.so"))]:
        f.unlink()
    return run_cmd(
        [
            [
                "cargo",
                "build",
                "-p",
                project_root.name,
                "--bins",
                "-r",
                "-Z",
                "unstable-options",
                "--artifact-dir",
                scripts_dir.as_posix(),
            ],
        ],
        f"Build and clean binaries for {project_root.name}",
    )


def make_dist_dir_publish() -> None:
    """Publish all packages in the dist directory."""
    success_count = 0
    for path in [f for f in DIST.iterdir() if f.is_file() and f.suffix in {".whl", ".tar.gz"}]:
        success = run_cmd(
            [["uv", "publish", path.as_posix()]],
            f"Publish {path.name}",
        )
        if success:
            logging.info(f"{path.name} publish succeeded.")
            success_count += 1
        else:
            logging.error(f"{path.name} publish failed.")
    logging.info(f"Successfully published {success_count} package(s).")


def make_dist(project_root: Union[str, Path]) -> bool:
    """Build a package using maturin."""
    project_root = Path(project_root)
    if is_using_maturin(project_root):
        for f in [*list(project_root.rglob("*.pyd")), *list(project_root.rglob("*.so"))]:
            f.unlink()
        return run_cmd(
            [
                [
                    "uvx",
                    "--python",
                    PYTHON_VERSION,
                    "--directory",
                    project_root.as_posix(),
                    "maturin",
                    "build",
                    "-o",
                    DIST.as_posix(),
                    "--sdist",
                ],
            ],
            f"Build {project_root.name}",
        )
    return run_cmd(
        [
            [
                "uv",
                "build",
                "--python",
                PYTHON_VERSION,
                "--package",
                project_root.name,
                "-o",
                DIST.as_posix(),
                "--sdist",
                "--wheel",
            ]
        ],
        f"Build {project_root.name}",
    )


def make_all(bins: bool, dev_mode: bool, bdist: bool, publish: bool) -> bool:
    """Build all packages that use maturin in parallel.

    Returns:
        True if all builds succeed, False otherwise.
    """
    futures = []
    for path in [d for d in (*list(PACKAGES_DIR.iterdir()), Path.cwd()) if d.is_dir()]:
        if is_using_maturin(path) and dev_mode:
            future = POOL.submit(make_maturin_dev, path)
            future.add_done_callback(lambda f, p=path: logging.info(f"Finished maturin dev build for {p.name}"))
            futures.append(future)
        if is_using_maturin(path) and bins and not bdist:
            future = POOL.submit(make_all_bins, path)
            future.add_done_callback(lambda f, p=path: logging.info(f"Finished binary build for {p.name}"))
            futures.append(future)
        if bdist or publish:
            future = POOL.submit(lambda p: make_all_bins(p) and make_dist(p), path)
            future.add_done_callback(lambda f, p=path: logging.info(f"Finished dist build for {p.name}"))
            futures.append(future)
    results = [future.result() for future in futures]
    if publish:
        make_dist_dir_publish()
    return all(results)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Build packages with customizable Python version.")
    parser.add_argument(
        "-py",
        "--pyversion",
        type=str,
        default=PYTHON_VERSION,
        help="Specify the Python version to use (e.g., '3.11'). Defaults to 3.13.",
    )
    parser.add_argument(
        "-b",
        "--bins",
        action="store_true",
        help="Build all binaries using Cargo and clean up debug files.",
    )
    parser.add_argument(
        "-d",
        "--dev",
        action="store_true",
        help="Build all packages using maturin in development mode.",
    )
    parser.add_argument(
        "-pub",
        "--publish",
        action="store_true",
        help="Publish all packages in the dist directory.",
    )
    parser.add_argument(
        "-bdist",
        "--bdist",
        action="store_true",
        help="Build all packages using maturin.",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    PYTHON_VERSION = args.pyversion
    logging.info(f"Using Python version: {PYTHON_VERSION}")
    success = make_all(
        bins=args.bins,
        dev_mode=args.dev,
        bdist=args.bdist,
        publish=args.publish,
    )
    if success:
        logging.info("All packages built successfully.")
    else:
        logging.error("One or more packages failed to build.")
