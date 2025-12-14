use crate::error::Error;
use crate::repo::REPO;
use colored::Colorize;
use human_units::iec::Byte;
use octocrab::models::repos::Asset;
use reqwest::Url;
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
            Byte::from_iec(self.source.size as u64)
                .format_iec()
                .to_string(),
            self.source.updated_at.to_string().bright_blue()
        )
    }
}

pub async fn show_releases() -> crate::error::Result<()> {
    let s = get_releases(Query::default())
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

pub(crate) async fn get_releases(query: Query) -> crate::error::Result<Vec<TemplateAssetItem>> {
    println!("Fetching releases...");
    Ok(REPO
        .releases()
        .list()
        .per_page(query.page_size)
        .page(query.page_num)
        .send()
        .await
        .map_err(Error::from)?
        .items
        .into_iter()
        .filter_map(|release| {
            release
                .assets
                .into_iter()
                .rev()
                .find(|asset| asset.name == TEMPLATES_ASSET_NAME)
                .map(|asset| TemplateAssetItem {
                    tag: release.tag_name,
                    source: asset,
                })
        })
        .collect())
}

/// Get asset url
pub async fn get_asset_url(version: Option<&str>) -> crate::error::Result<Url> {
    let releases = get_releases(Query::default()).await?;

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
