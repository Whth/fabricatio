use colored::Colorize;
use indicatif::{ProgressBar, ProgressStyle};
use reqwest::blocking::Client;
use std::fs;
use std::fs::File;
use std::io::Write;
use std::path::PathBuf;

pub fn handle_download(
    client: &Client,
    output_dir: &PathBuf,
    keep_archive: &bool,
    version: Option<&str>,
    download_only: bool,
    verbose: bool,
) -> Result<(), Box<dyn std::error::Error>> {
    let path = PathBuf::from(output_dir);
    fs::create_dir_all(&path)?;

    if verbose {
        println!("{} Starting download...", "Download".blue());
    }

    let (download_url, tar_gz_path) = prepare_download(client, version, &path)?;
    download_release(client, &download_url, &tar_gz_path, verbose)?;

    if !download_only {
        crate::extract_release(&tar_gz_path, &path, verbose)?;

        if !keep_archive {
            if verbose {
                println!("{} Cleaning up archive file...", "Cleanup".yellow());
            }
            fs::remove_file(&tar_gz_path)?;
        }
    }

    println!("{} Download completed successfully", "✓".green());
    Ok(())
}

pub fn download_release(
    client: &Client,
    download_url: &str,
    output_path: &PathBuf,
    verbose: bool,
) -> Result<(), Box<dyn std::error::Error>> {
    if verbose {
        println!("{} {}", "Downloading".green(), download_url);
    }

    let response = client
        .get(download_url)
        .header("User-Agent", "fabricatio_template_downloader")
        .send()?;

    if !response.status().is_success() {
        return Err(format!("Failed to download file: {}", response.status()).into());
    }

    let total_size = response.content_length().unwrap_or(0);
    let mut downloaded = 0u64;
    let mut file = File::create(output_path)?;

    let pb = if verbose && total_size > 0 {
        let pb = ProgressBar::new(total_size);
        pb.set_style(ProgressStyle::default_bar()
            .template("{spinner:.green} [{elapsed_precise}] [{wide_bar:.cyan/blue}] {bytes}/{total_bytes} ({eta})")
            .unwrap()
            .progress_chars("#>-"));
        Some(pb)
    } else {
        None
    };

    if let Ok(chunk) = response.bytes() {
        file.write_all(&chunk)?;
        downloaded += chunk.len() as u64;
        if let Some(ref pb) = pb {
            pb.set_position(downloaded);
        }
    }

    if let Some(pb) = pb {
        pb.finish_with_message("Download completed");
    } else if verbose {
        println!("{} Download completed", "✓".green());
    }

    Ok(())
}

pub fn prepare_download(
    client: &Client,
    version: Option<&str>,
    output_dir: &PathBuf,
) -> Result<(String, PathBuf), Box<dyn std::error::Error>> {
    let latest_release = crate::retrieve_release(client, version)?;
    let assets = latest_release["assets"]
        .as_array()
        .ok_or("No assets found in release")?;

    let tar_gz_asset = assets
        .iter()
        .find(|asset| asset["name"] == "templates.tar.gz")
        .ok_or("templates.tar.gz not found in the latest release")?;

    let download_url = tar_gz_asset["browser_download_url"]
        .as_str()
        .ok_or("Download URL not found")?
        .to_string();

    let tar_gz_path = output_dir.join("templates.tar.gz");

    Ok((download_url, tar_gz_path))
}

pub fn handle_update(
    client: &Client,
    template_dir: &PathBuf,
    backup: bool,
    verbose: bool,
) -> Result<(), Box<dyn std::error::Error>> {
    if backup {
        crate::create_backup(template_dir, verbose)?;
    }

    let (download_url, tar_gz_path) = prepare_download(client, None, template_dir)?;
    download_release(client, &download_url, &tar_gz_path, verbose)?;
    crate::extract_release(&tar_gz_path, template_dir, verbose)?;
    fs::remove_file(tar_gz_path)?;

    println!("{} Update completed successfully", "✓".green());
    Ok(())
}
