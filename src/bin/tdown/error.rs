use std::time::SystemTimeError;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum Error {
    #[error("Failed to get release info: {0}")]
    ReleaseInfo(#[from] octocrab::Error),

    #[error("Failed to retrieve from cache: {0}")]
    Cache(#[from] cached::DiskCacheError),

    #[error("Release not found, please check the version number.")]
    ReleaseNotFound,

    #[error("Io Error: {0}")]
    IO(#[from] std::io::Error),

    #[error("Network Error: {0}")]
    Network(#[from] reqwest::Error),

    #[error("Failed to parse time: {0}")]
    TimeParse(#[from] SystemTimeError),

    #[error("Failed to render template: {0}")]
    Render(#[from] indicatif::style::TemplateError),
}

pub type Result<T> = std::result::Result<T, Error>;
