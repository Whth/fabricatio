# Fabricatio Constants

A foundational constants crate for the Fabricatio ecosystem, providing application-wide constants, paths, and
configuration variables.

## Overview

This crate centralizes all constants used across the Fabricatio project, including application names, configuration file
paths, directory locations, and environment variable names. It ensures consistency and provides a single source of truth
for these values.

## Features

- **Application Constants**: Centralized definitions for application name, repository details, and core package names
- **Path Management**: Automatic determination of user configuration directories across different operating systems
- **Template Support**: Constants for template directory management and global configuration files
- **Environment Variables**: Standardized names for configuration and logging variables

## Platform Support

The crate automatically detects the user's operating system and provides appropriate paths:

| Platform | Config Directory                      | Example                                               |
|----------|---------------------------------------|-------------------------------------------------------|
| Linux    | `$XDG_CONFIG_HOME` or `$HOME/.config` | `/home/alice/.config/fabricatio`                      |
| macOS    | `$HOME/Library/Application Support`   | `/Users/Alice/Library/Application Support/fabricatio` |
| Windows  | `{FOLDERID_RoamingAppData}`           | `C:\Users\Alice\AppData\Roaming\fabricatio`           |

## Constants

### Application Constants

- `NAME`: Application name ("fabricatio")
- `CORE_PACKAGE_NAME`: Core package name ("fabricatio_core")
- `REPO_OWNER`: GitHub repository owner ("Whth")
- `REPO_NAME`: Repository name (same as NAME)

### Path Constants

- `CONFIG_FILE`: Default configuration filename ("fabricatio.toml")
- `TEMPLATES_DIRNAME`: Templates directory name ("templates")
- `ROAMING`: Global roaming configuration directory
- `TEMPLATES`: Templates directory within roaming config
- `GLOBAL_CONFIG_FILE`: Full path to global configuration file

### Environment Variables

- `LOGGER_VARNAME`: Logger configuration variable name ("logger")
- `CONFIG_VARNAME`: Configuration variable name ("CONFIG")
- `PY_SOURCE_KEY`: Python source code path key ("py_source")

## Usage

```rust
use fabricatio_constants::{NAME, ROAMING, GLOBAL_CONFIG_FILE};

fn main() {
    println!("Application: {}", NAME);
    println!("Config directory: {:?}", ROAMING);
    println!("Config file: {:?}", GLOBAL_CONFIG_FILE);
}
```

## Dependencies

- `once_cell`: For global static lazy initialization
- `directories-next`: Cross-platform directory configuration

## License

This crate is part of the Fabricatio project and follows the same licensing terms.