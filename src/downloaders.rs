use clap::Parser;
use reqwest::blocking::Client;
use std::fs::File;
use std::path::PathBuf;
use tar::Archive;
use flate2::read::GzDecoder;

#[derive(Parser)]
#[command(name = "fabricatio_cli")]
#[command(version = "0.1")]
#[command(about = "CLI tool to download and extract templates.tar.gz from GitHub.", long_about = None)]
struct Cli {
    #[arg(long, default_value_t = String::from("templates"))]
    output_dir: String,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    let output_path = PathBuf::from(&cli.output_dir);

    // 下载文件
    let client = Client::new();
    let repo_url = "https://api.github.com/repos/Whth/fabricatio/releases/latest";
    let response = client.get(repo_url).send()?;
    let latest_release: serde_json::Value = response.json()?;
    let assets = latest_release["assets"].as_array().unwrap();
    let tar_gz_asset = assets.iter().find(|asset| asset["name"] == "templates.tar.gz");

    if let Some(asset) = tar_gz_asset {
        let download_url = asset["browser_download_url"].as_str().unwrap();
        let tar_gz_path = output_path.join("templates.tar.gz");

        println!("Downloading {}...", download_url);
        let mut response = client.get(download_url).send()?;
        let mut file = File::create(&tar_gz_path)?;
        std::io::copy(&mut response, &mut file)?;

        // 解压文件
        println!("Extracting to {}...", cli.output_dir);
        let tar_gz = File::open(tar_gz_path)?;
        let decoder = GzDecoder::new(tar_gz);
        let mut archive = Archive::new(decoder);
        archive.unpack(&output_path)?;
    } else {
        println!("templates.tar.gz not found in the latest release.");
    }

    Ok(())
}
