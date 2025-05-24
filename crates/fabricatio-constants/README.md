# `fabricatio-constants`

This crate provides constant values used throughout the `fabricatio` application.

## Constants

- `NAME`: The name of the application, "fabricatio".
- `ROAMING`: The directory where application-specific configuration data is stored.
- `TEMPLATES`: A subdirectory of `ROAMING`, used to store template files.

The `ROAMING` and `TEMPLATES` directories are lazily initialized upon first use.