//! # Fabricatio Constants
//!
//! A foundational constants crate for the Fabricatio ecosystem, providing application-wide constants, paths, and configuration variables.
//!
//! This crate centralizes all constants used across the Fabricatio project, including application names, configuration file paths, directory locations, and environment variable names. It ensures consistency and provides a single source of truth for these values.
//!
//! ## Features
//!
//! - **Application Constants**: Centralized definitions for application name, repository details, and core package names
//! - **Path Management**: Automatic determination of user configuration directories across different operating systems
//! - **Template Support**: Constants for template directory management and global configuration files
//! - **Environment Variables**: Standardized names for configuration and logging variables
//!
//! ## Platform Support
//!
//! The crate automatically detects the user's operating system and provides appropriate paths:
//!
//! | Platform | Config Directory | Example |
//! |----------|------------------|----------|
//! | Linux | `$XDG_CONFIG_HOME` or `$HOME/.config` | `/home/alice/.config/fabricatio` |
//! | macOS | `$HOME/Library/Application Support` | `/Users/Alice/Library/Application Support/fabricatio` |
//! | Windows | `{FOLDERID_RoamingAppData}` | `C:\Users\Alice\AppData\Roaming\fabricatio` |
//!
//! ## Usage
//!
//! ```rust
//! use fabricatio_constants::{NAME, ROAMING, GLOBAL_CONFIG_FILE};
//!
//! fn main() {
//!     println!("Application: {}", NAME);
//!     println!("Config directory: {:?}", ROAMING);
//!     println!("Config file: {:?}", GLOBAL_CONFIG_FILE);
//! }
//! ```
//!
//! For more information, see the [README](https://github.com/Whth/fabricatio/blob/main/crates/fabricatio-constants/README.md).

use directories_next::BaseDirs;
use once_cell::sync::Lazy;
use std::path::PathBuf;

/// The application name used across the project.
pub const NAME: &str = "fabricatio";

/// The name of the core package used by the application.
pub const CORE_PACKAGE_NAME: &str = "fabricatio_core";

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
/// The name of the templates' directory.
pub const TEMPLATES_DIRNAME: &str = "templates";
/// A global static instance of the templates directory located within the roaming configuration directory.
pub static TEMPLATES: Lazy<PathBuf> = Lazy::new(|| ROAMING.join(TEMPLATES_DIRNAME));
/// A global static instance of the global configuration file path, constructed by joining
/// the roaming directory with the application-specific configuration file name.
pub static GLOBAL_CONFIG_FILE: Lazy<PathBuf> = Lazy::new(|| ROAMING.join(CONFIG_FILE));

/// The name of the logger variable used by the application.
pub const LOGGER_VARNAME: &str = "logger";
/// The name of the configuration variable used by the application.
pub const CONFIG_VARNAME: &str = "CONFIG";
/// The key used to store the Python source code path.
pub const PY_SOURCE_KEY: &str = "py_source";
