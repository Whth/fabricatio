# `fabricatio-constants`

This crate provides constant values used throughout the `fabricatio` application.

## Constants

- `NAME`: The name of the application, "fabricatio".
- `CONFIG_FILE`: The name of the global configuration file, "fabricatio.toml".
- `ROAMING`: The directory where application-specific configuration data is stored.
- `TEMPLATES`: A subdirectory of `ROAMING`, used to store template files.
- `GLOBAL_CONFIG_FILE`: The full path to the global configuration file.

The `ROAMING`, `TEMPLATES`, and `GLOBAL_CONFIG_FILE` directories/paths are lazily initialized upon first use.

## Directory Locations

The `ROAMING` directory is determined based on the operating system:

| Platform | Directory Example                                                                                            |
|----------|--------------------------------------------------------------------------------------------------------------|
| Linux    | `$XDG_CONFIG_HOME/fabricatio` or `$HOME/.config/fabricatio` (e.g., `/home/alice/.config/fabricatio`)         |
| macOS    | `$HOME/Library/Application Support/fabricatio` (e.g., `/Users/Alice/Library/Application Support/fabricatio`) |
| Windows  | `%APPDATA%\fabricatio` (e.g., `C:\Users\Alice\AppData\Roaming\fabricatio`)                                   |

- `TEMPLATES` will be a `templates` subdirectory inside the above.
- `GLOBAL_CONFIG_FILE` will be `fabricatio.toml` inside the above.

These paths are resolved using the [directories-next](https://docs.rs/directories-next/) crate.