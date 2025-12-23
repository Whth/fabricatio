use directories_next::BaseDirs;
use once_cell::sync::Lazy;
use std::path::PathBuf;

/// The application name used across the project.
pub const NAME: &str = "fabricatio";

/// The default configuration file name used by the application.
pub const CONFIG_FILE: &str = "fabricatio.toml";

/// The GitHub repository owner for the application.
pub const REPO_OWNER: &str = "Whth";

/// The GitHub repository name for the application.
pub const REPO_NAME: &str = NAME;

/// Returns the path to the user's config directory based on the operating system.
///
/// |Platform | Value                                 | Example                          |
/// | ------- | ------------------------------------- | -------------------------------- |
/// | Linux   | `$XDG_CONFIG_HOME` or `$HOME`/.config/<APPNAME> | /home/alice/.config/app              |
/// | macOS   | `$HOME`/Library/Application Support/<APPNAME>   | /Users/Alice/Library/Application Support/app |
/// | Windows | `{FOLDERID_RoamingAppData}\<APPNAME>`           | C:\Users\Alice\AppData\Roaming\app   |
///
/// # Arguments
/// * `app_name` - The name of the application used when constructing the directory path.
///
/// # Returns
/// An `Option<PathBuf>` representing the roaming directory if available.
fn get_roaming_dir(app_name: &str) -> Option<PathBuf> {
    BaseDirs::new().map(|dirs| dirs.config_dir().join(app_name))
}

/// A global static instance of the user's roaming configuration directory for the application.
pub static ROAMING: Lazy<PathBuf> =
    Lazy::new(|| get_roaming_dir(NAME).expect("Failed to get roaming directory"));

/// A global static instance of the templates directory located within the roaming configuration directory.
pub static TEMPLATES: Lazy<PathBuf> = Lazy::new(|| ROAMING.join("templates"));

/// A global static instance of the global configuration file path, constructed by joining
/// the roaming directory with the application-specific configuration file name.
pub static GLOBAL_CONFIG_FILE: Lazy<PathBuf> = Lazy::new(|| ROAMING.join(CONFIG_FILE));
