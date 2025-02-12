import os
import shutil
import subprocess
import tarfile

import requests
import typer

app = typer.Typer()


def download_file(url: str, destination: str) -> None:
    """Download a file from a given URL to a specified destination.

    Args:
        url (str): The URL of the file to download.
        destination (str): The path where the file should be saved.

    Raises:
        requests.exceptions.HTTPError: If the request to the URL fails.
    """
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(destination, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def extract_tar_gz(file_path: str, extract_to: str) -> None:
    """Extract a tar.gz file to a specified directory.

    Args:
        file_path (str): The path to the tar.gz file.
        extract_to (str): The directory where the contents should be extracted.
    """
    with tarfile.open(file_path, "r:gz") as tar:
        tar.extractall(path=extract_to)


def extract_with_7z(file_path: str, extract_to: str) -> None:
    """Extract a file using the 7z command-line tool.

    Args:
        file_path (str): The path to the file to extract.
        extract_to (str): The directory where the contents should be extracted.

    Raises:
        subprocess.CalledProcessError: If the 7z command fails.
    """
    subprocess.run(["7z", "x", file_path, f"-o{extract_to}"], check=True)


@app.command()
def download_and_extract(output_dir: str = typer.Argument(..., help="Directory to extract the templates to")) -> None:
    """Download and extract the templates.tar.gz file from the latest release of the fabricatio GitHub repository.

    Args:
        output_dir (str): The directory where the templates should be extracted.

    Raises:
        typer.Exit: If the templates.tar.gz file is not found or extraction fails.
    """
    repo_url = "https://api.github.com/repos/Whth/fabricatio/releases/latest"
    response = requests.get(repo_url)
    response.raise_for_status()
    latest_release = response.json()
    assets = latest_release.get("assets", [])
    tar_gz_asset = next((asset for asset in assets if asset["name"] == "templates.tar.gz"), None)

    if not tar_gz_asset:
        typer.echo("templates.tar.gz not found in the latest release.")
        raise typer.Exit(code=1)

    download_url = tar_gz_asset["browser_download_url"]
    tar_gz_path = os.path.join(output_dir, "templates.tar.gz")

    download_file(download_url, tar_gz_path)
    typer.echo(f"Downloaded {download_url} to {tar_gz_path}")

    try:
        if shutil.which("7z"):
            extract_with_7z(tar_gz_path, output_dir)
        elif shutil.which("tar"):
            extract_tar_gz(tar_gz_path, output_dir)
        else:
            typer.echo("Neither 7z nor tar is available for extraction.")
            raise typer.Exit(code=1)
        typer.echo(f"Extracted templates to {output_dir}")
    except Exception as e:
        typer.echo(f"Extraction failed: {e}")
        raise typer.Exit(code=1)
