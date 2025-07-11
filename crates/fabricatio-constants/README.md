# `fabricatio-constants`

This crate provides constant values used throughout the `fabricatio` application.

## Constants

- `NAME`: The name of the application, "fabricatio".
- `CONFIG_FILE`: The name of the global configuration file, "fabricatio.toml".
- `ROAMING`: The directory where application-specific configuration data is stored.
- `TEMPLATES`: A subdirectory of `ROAMING`, used to store template files.
- `GLOBAL_CONFIG_FILE`: The full path to the global configuration file.

The `ROAMING`, `TEMPLATES`, and `GLOBAL_CONFIG_FILE` directories/paths are lazily initialized upon first use.
