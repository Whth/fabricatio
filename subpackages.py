"""Build packages with customizable Python version."""

from pathlib import Path

import argparse
import logging
import subprocess
import tomllib
from concurrent.futures.thread import ThreadPoolExecutor
from typing import List, Optional, Union

PACKAGES_DIR = (Path.cwd() / "packages").absolute()
DIST = (Path.cwd() / "dist").absolute()
SCRIPTS_DIR = Path("extra") / "scripts"
LOG_DIR = (Path.cwd() / "logs").absolute()

PYTHON_VERSION = "3.13"

POOL = ThreadPoolExecutor()


def run_cmd(cmd_sequence: List[List[str]], desc: str, log_file: Optional[Path] = None,
            cwd: Optional[Path] = None) -> bool:
    """Run a sequence of shell commands and log output.

    Args:
        cmd_sequence: A list of command sequences to execute.
        desc: Description of the command being executed for logging.
        log_file: Optional path to a file where stderr and stdout should be redirected.
        cwd: Optional path to a directory where the command should be executed.
    Returns:
        True if all commands succeed, False otherwise.
    """
    try:
        for cmd in cmd_sequence:
            logging.info(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8",
                                    cwd=cwd)  # noqa: S603
            if log_file:
                with log_file.open("a", encoding="utf-8") as f:
                    f.write(f"Command: {' '.join(cmd)}\n")
                    f.write(f"Stdout:\n{result.stdout}\n")
                    f.write(f"Stderr:\n{result.stderr}\n")
                    f.write("-" * 50 + "\n")
            logging.info(f"Command output: {' '.join(cmd)} \n{result.stdout}")
        logging.info(f"{desc} completed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error occurred during '{desc}': {e.stderr}")
        if log_file:
            with log_file.open("a", encoding="utf-8") as f:
                f.write(f"Error during '{desc}': {e.stderr}\n")
                f.write("-" * 50 + "\n")
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
    log_file = LOG_DIR / f"{project_root.name}_dev.log"

    return run_cmd(
        [["uvx", "maturin", "develop", "-r", "--uv"]],
        f"maturin develop mode for {project_root.name}",
        log_file=log_file,
        cwd=project_root
    )


def make_all_bins(project_root: Union[str, Path]) -> bool:
    """Build all binaries using Cargo and clean up debug files.

    Args:
        project_root: The root directory of the project.

    Returns:
        True if the operation succeeds, False otherwise.
    """
    project_root = Path(project_root)
    log_file = LOG_DIR / f"{project_root.name}_bins.log"

    scripts_dir = project_root.joinpath(SCRIPTS_DIR)
    scripts_dir.mkdir(parents=True, exist_ok=True)
    ret = run_cmd(
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
        log_file=log_file,
    )
    for f in [*list(scripts_dir.rglob("*.pdb")), *list(scripts_dir.rglob("*.dwarf"))]:
        f.unlink()
    return ret


def make_dist_dir_publish() -> None:
    """Publish all packages in the dist directory."""
    success_count = 0
    for path in [f for f in DIST.iterdir() if f.is_file() and f.suffix in {".whl", ".tar.gz"}]:
        log_file = LOG_DIR / f"publish_{path.stem}.log"
        suc = run_cmd(
            [["uv", "publish", path.as_posix()]],
            f"Publish {path.name}",
            log_file=log_file,
        )
        if suc:
            logging.info(f"{path.name} publish succeeded.")
            success_count += 1
        else:
            logging.error(f"{path.name} publish failed.")
    logging.info(f"Successfully published {success_count} package(s).")


def make_dist(project_root: Union[str, Path]) -> bool:
    """Build a package using maturin."""
    project_root = Path(project_root)
    log_file = LOG_DIR / f"{project_root.name}_dist.log"
    if is_using_maturin(project_root):
        src_dir = project_root / "python"
        for f in [*list(src_dir.rglob("*.pyd")), *list(src_dir.rglob("*.so"))]:
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
                    "--strip",
                ],
            ],
            f"Build {project_root.name}",
            log_file=log_file,
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
        log_file=log_file,
    )


def _pack(project_root: str | Path) -> bool:
    return make_all_bins(project_root) and make_dist(project_root)


def _dev(project_root: str | Path) -> bool:
    return make_all_bins(project_root) and make_maturin_dev(project_root)


def make_all(bins: bool, dev_mode: bool, bdist: bool, publish: bool) -> bool:
    """Build all packages that use maturin in parallel.

    Returns:
        True if all builds succeed, False otherwise.
    """
    futures = []
    for path in [d for d in (*list(PACKAGES_DIR.iterdir()), Path.cwd()) if d.is_dir()]:

        if bdist or publish:
            future = POOL.submit(_pack if is_using_maturin(path) else make_dist, path)
            future.add_done_callback(lambda f, p=path: logging.info(f"Finished dist build for {p.name}"))
            futures.append(future)
        elif is_using_maturin(path):
            if dev_mode:
                future = POOL.submit(_dev, path)
                future.add_done_callback(lambda f, p=path: logging.info(f"Finished maturin dev build for {p.name}"))
                futures.append(future)
            elif bins:
                future = POOL.submit(make_all_bins, path)
                future.add_done_callback(lambda f, p=path: logging.info(f"Finished binary build for {p.name}"))
                futures.append(future)
        else:
            logging.info(f"{path.name} is not using maturin, skipping...")

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
    parser.add_argument(
        "-dd",
        "--distdir",
        type=str,
        default=DIST.as_posix(),
        help=f"Specify the distribution directory to store built packages. Defaults to {DIST.as_posix()}",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    PYTHON_VERSION = args.pyversion
    DIST_DIR = Path(args.distdir).absolute()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.info(f"Using Python version: {PYTHON_VERSION}")
    logging.info(f"Using distribution directory: {DIST_DIR.as_posix()}")
    logging.info(f"Using log directory: {LOG_DIR.as_posix()}")
    # Update DIST global variable based on command line argument
    globals()['DIST'] = DIST_DIR
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
