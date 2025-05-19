use directories_next::BaseDirs;
use lazy_static::lazy_static;
use std::path::PathBuf;

fn get_roaming_dir(app_name: &str) -> Option<PathBuf> {
    BaseDirs::new().map(|dirs| dirs.config_dir().join(app_name))
}

pub const NAME: &str = "fabricatio";

lazy_static! {
    pub static ref ROAMING: PathBuf = get_roaming_dir(NAME).expect("Failed to get roaming dir");
    pub static ref TEMPLATES: PathBuf = ROAMING.join("templates");
}
