use directories_next::BaseDirs;
use once_cell::sync::Lazy;
use std::path::PathBuf;

pub const NAME: &str = "fabricatio";

fn get_roaming_dir(app_name: &str) -> Option<PathBuf> {
    BaseDirs::new().map(|dirs| dirs.config_dir().join(app_name))
}

pub static ROAMING: Lazy<PathBuf> =
    Lazy::new(|| get_roaming_dir(NAME).expect("Failed to get roaming directory"));

pub static TEMPLATES: Lazy<PathBuf> = Lazy::new(|| ROAMING.join("templates"));
