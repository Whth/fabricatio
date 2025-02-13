import shutil
import subprocess
import tarfile
from pathlib import Path

import requests
import typer

from fabricatio.config import ROAMING_DIR

app = typer.Typer()


def download_file(url: str, destination: Path) -> None:
    """Download a file from a given URL to a specified destination.

    Args:
        url (str): The URL of the file to download.
        destination (Path): The path where the file should be saved.

    Raises:
        requests.exceptions.HTTPError: If the request to the URL fails.
    """
    response = requests.get(url, stream=True, timeout=120)
    response.raise_for_status()
    with destination.open("wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def extract_tar_gz(file_path: Path, extract_to: Path) -> None:
    """Extract a tar.gz file to a specified directory.

    Args:
        file_path (Path): The path to the tar.gz file.
        extract_to (Path): The directory where the contents should be extracted.
    """
    with tarfile.open(file_path, "r:gz") as tar:
        tar.extractall(path=extract_to, filter="data")


def extract_with_7z(file_path: Path, extract_to: Path) -> None:
    """Extract a file using the 7z command-line tool.

    Args:
        file_path (Path): The path to the file to extract.
        extract_to (Path): The directory where the contents should be extracted.

    Raises:
        subprocess.CalledProcessError: If the 7z command fails.
    """
    subprocess.run(["7z", "x", file_path, f"-o{extract_to}"], check=True)  # noqa: S603, S607


@app.command()
def download_and_extract(
    output_dir: str = typer.Argument(default=ROAMING_DIR, help="Directory to extract the templates to"),
) -> None:
    """Download and extract the templates.tar.gz file from the latest release of the fabricatio GitHub repository.

    Args:
        output_dir (str): The directory where the templates should be extracted.

    Raises:
        typer.Exit: If the templates.tar.gz file is not found or extraction fails.
    """
    repo_url = "https://api.github.com/repos/Whth/fabricatio/releases/latest"
    response = requests.get(repo_url, timeout=30)
    response.raise_for_status()
    latest_release = response.json()
    assets = latest_release.get("assets", [])
    tar_gz_asset = next((asset for asset in assets if asset["name"] == "templates.tar.gz"), None)

    if not tar_gz_asset:
        typer.echo("templates.tar.gz not found in the latest release.")
        raise typer.Exit(code=1)

    download_url = tar_gz_asset["browser_download_url"]
    output_path = Path(output_dir)  # Convert output_dir to Path object
    tar_gz_path = output_path.joinpath("templates.tar.gz")  # Use joinpath instead of os.path.join

    download_file(download_url, tar_gz_path)  # Directly use Path object
    typer.echo(f"Downloaded {download_url} to {tar_gz_path}")

    try:
        if shutil.which("7z"):
            extract_with_7z(tar_gz_path, output_path)  # Directly use Path objects
        elif shutil.which("tar"):
            extract_tar_gz(tar_gz_path, output_path)  # Directly use Path objects
        else:
            typer.echo("Neither 7z nor tar is available for extraction.")
            raise typer.Exit(code=1)
        typer.echo(f"Extracted templates to {output_dir}")
    except RuntimeError as e:
        typer.echo(f"Extraction failed: {e}")
        raise typer.Exit(code=1) from e
