use crate::releases::TEMPLATES_ASSET_NAME;
use colored::Colorize;
use indicatif::{ProgressBar, ProgressStyle};
use reqwest::Client;
use reqwest::Url;
use std::fs;
use std::fs::File;
use std::io::Write;
use std::path::PathBuf;

pub async fn handle_download(
    client: &Client,
    output_dir: &PathBuf,
    version: Option<&str>,
    verbose: bool,
) -> crate::error::Result<()> {
    let path = PathBuf::from(output_dir);
    fs::create_dir_all(&path)?;

    if verbose {
        println!("{} Starting download...", "Download".blue());
    }

    let tar_gz_path = output_dir.join(TEMPLATES_ASSET_NAME);
    let download_url = crate::releases::get_asset_url(version).await?;

    download_release(client, &download_url, &tar_gz_path, verbose).await?;

    crate::extract_release(&tar_gz_path, &path, verbose)?;
    fs::remove_file(&tar_gz_path)?;

    println!("{} Download completed successfully", "✓".green());
    Ok(())
}

pub async fn download_release(
    client: &Client,
    download_url: &Url,
    output_path: &PathBuf,
    verbose: bool,
) -> crate::error::Result<()> {
    if verbose {
        println!("{} {}", "Downloading".green(), download_url);
    }

    let response = client.get(download_url.as_str()).send().await?;

    let total_size = response.content_length().unwrap_or(0);
    let mut downloaded = 0u64;
    let mut file = File::create(output_path)?;

    let pb = if verbose && total_size > 0 {
        let pb = ProgressBar::new(total_size);
        pb.set_style(ProgressStyle::default_bar()
            .template("{spinner:.green} [{elapsed_precise}] [{wide_bar:.cyan/blue}] {bytes}/{total_bytes} ({eta})")?
            .progress_chars("#>-"));
        Some(pb)
    } else {
        None
    };

    if let Ok(chunk) = response.bytes().await {
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

pub async fn handle_update(
    client: &Client,
    template_dir: &PathBuf,
    backup: bool,
    verbose: bool,
) -> crate::error::Result<()> {
    if backup {
        crate::create_backup(template_dir, verbose)?;
    }

    let tar_gz_path = template_dir.join(TEMPLATES_ASSET_NAME);

    let download_url = crate::releases::get_asset_url(None).await?;
    download_release(client, &download_url, &tar_gz_path, verbose).await?;
    crate::extract_release(&tar_gz_path, template_dir, verbose)?;
    fs::remove_file(tar_gz_path)?;

    println!("{} Update completed successfully", "✓".green());
    Ok(())
}
