use crate::error::Error;
use colored::Colorize;
use fabricatio_constants::{REPO_NAME, REPO_OWNER};
use human_units::iec::Byte;
use reqwest::{Client, Url};
use serde::Deserialize;
use std::fmt::Display;

pub const TEMPLATES_ASSET_NAME: &str = "templates.tar.gz";

#[derive(Debug)]
pub(crate) struct TemplateAssetItem {
    tag: String,
    source: Asset,
}

impl Display for TemplateAssetItem {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{:<15}  {:<6}  {:}",
            self.tag.to_string().bright_green(),
            Byte::from_iec(self.source.size).format_iec().to_string(),
            self.source.updated_at.to_string().bright_blue()
        )
    }
}

#[derive(Debug, Deserialize)]
struct Release {
    tag_name: String,
    assets: Vec<Asset>,
}

#[derive(Debug, Deserialize)]
struct Asset {
    name: String,
    size: u64,
    updated_at: String,
    browser_download_url: Url,
}

fn releases_url() -> Url {
    Url::parse(&format!(
        "https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases"
    ))
    .expect("static GitHub releases URL is valid")
}

pub async fn show_releases(client: &Client) -> crate::error::Result<()> {
    let s = get_releases(client, Query::default())
        .await?
        .into_iter()
        .map(|item| item.to_string())
        .collect::<Vec<String>>()
        .join("\n");

    if s.is_empty() {
        println!("No releases found.");
        return Ok(());
    }

    print!("{}", s);
    Ok(())
}

#[derive(Debug, Clone)]
pub(crate) struct Query {
    page_size: u8,
    page_num: u32,
}

impl Default for Query {
    fn default() -> Self {
        Self {
            page_size: 10,
            page_num: 1,
        }
    }
}

pub(crate) async fn get_releases(
    client: &Client,
    query: Query,
) -> crate::error::Result<Vec<TemplateAssetItem>> {
    println!("Fetching releases...");

    let params = [
        ("per_page", query.page_size.to_string()),
        ("page", query.page_num.to_string()),
    ];
    let releases: Vec<Release> = client
        .get(releases_url())
        .query(&params)
        .send()
        .await?
        .error_for_status()?
        .json()
        .await?;

    Ok(releases
        .into_iter()
        .filter_map(|release| {
            let Release { tag_name, assets } = release;
            assets
                .into_iter()
                .rev()
                .find(|asset| asset.name == TEMPLATES_ASSET_NAME)
                .map(|asset| TemplateAssetItem {
                    tag: tag_name,
                    source: asset,
                })
        })
        .collect())
}

/// Get asset url
pub async fn get_asset_url(client: &Client, version: Option<&str>) -> crate::error::Result<Url> {
    let releases = get_releases(client, Query::default()).await?;

    let url = if let Some(v) = version {
        releases
            .into_iter()
            .find(|item| item.tag == v)
            .ok_or_else(|| Error::ReleaseNotFound)
            .map(|item| item.source.browser_download_url)
    } else {
        releases
            .first()
            .map(|item| item.source.browser_download_url.clone())
            .ok_or_else(|| Error::ReleaseNotFound)
    }?;
    Ok(url)
}
