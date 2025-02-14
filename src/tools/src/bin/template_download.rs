use clap::Parser;
use flate2::read::GzDecoder;
use reqwest::blocking::Client;
use std::fs::File;
use std::path::PathBuf;
use tar::Archive;

use dirs::config_dir;


fn get_dir() -> String {
    config_dir().unwrap().join("fabricatio").to_string_lossy().to_string()
}

/// A command-line interface for downloading templates.
#[derive(Parser)]
#[command(name = "fabricatio_template_downloader", author)]
struct Cli {
    /// The directory to output the templates to.
    #[arg(short, long, default_value_t = get_dir())]
    output_dir: String,
}

fn retrieve_release(client: &Client) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    let repo_url = "https://api.github.com/repos/Whth/fabricatio/releases/latest";
    let response = client
        .get(repo_url)
        .header("User-Agent", "fabricatio_template_downloader")
        .send()?;

    // Attempt to parse the JSON
    Ok(response.json()?)
}

fn download_release(client: &Client, download_url: &str, output_path: &PathBuf) -> Result<(), Box<dyn std::error::Error>> {
    println!("Downloading {}...", download_url);
    let mut response = client.get(download_url).send()?;
    let mut file = File::create(output_path)?;
    std::io::copy(&mut response, &mut file)?;
    Ok(())
}

fn extract_release(tar_gz_path: &PathBuf, output_dir: &PathBuf) -> Result<(), Box<dyn std::error::Error>> {
    println!("Extracting to {}...", output_dir.display());
    let tar_gz = File::open(tar_gz_path)?;
    let decoder = GzDecoder::new(tar_gz);
    let mut archive = Archive::new(decoder);
    archive.unpack(output_dir)?;
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    let client = Client::new();
    let path = PathBuf::from(cli.output_dir);
    println!("Starting download...");

    // Retrieve release information
    let latest_release = retrieve_release(&client)?;
    let assets = latest_release["assets"].as_array().unwrap();
    let tar_gz_asset = assets.iter().find(|asset| asset["name"] == "templates.tar.gz");

    if let Some(asset) = tar_gz_asset {
        let download_url = asset["browser_download_url"].as_str().unwrap();
        let tar_gz_path = path.join("templates.tar.gz");

        // Download and extract the release
        download_release(&client, download_url, &tar_gz_path)?;
        extract_release(&tar_gz_path, &path)?;

        // Delete the compressed file after extraction
        println!("Deleting compressed file...");
        std::fs::remove_file(&tar_gz_path)?;
    } else {
        println!("templates.tar.gz not found in the latest release.");
    }

    Ok(())
}