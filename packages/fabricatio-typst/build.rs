use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

fn main() {
    // Get the DATA environment variable, use "extra" as default if not set
    let data_dir: PathBuf = PathBuf::from("extra");

    // Construct the target directory extra/scripts
    let artifact_dir = data_dir.join("scripts");

    // If the scripts directory already exists and is not empty, exit directly
    if artifact_dir.exists() {
        match fs::read_dir(&artifact_dir) {
            Ok(mut entries) => {
                if let Some(Ok(first_entry)) = entries.next() {
                    let first_file_name = first_entry.file_name();
                    println!(
                        "cargo:warning=Scripts directory {} is not empty (e.g., found {}), exiting build script.",
                        artifact_dir.display(),
                        first_file_name.to_string_lossy()
                    );
                    return;
                }
            }
            Err(e) => {
                // It's probably better to panic here if we can't read the directory,
                // as it might indicate a permissions issue or other problem.
                // However, if the goal is just to rebuild if unsure, one might choose to proceed.
                // Given the context of a build script, panicking on unexpected errors is safer.
                panic!(
                    "Failed to read artifact directory {}: {}",
                    artifact_dir.display(),
                    e
                );
            }
        }
    }

    // Create the output directory
    if let Err(e) = fs::create_dir_all(&artifact_dir) {
        panic!(
            "Failed to create artifact directory {}: {}",
            artifact_dir.display(),
            e
        );
    }
    println!("cargo:warning=Start building tools");

    // Execute the cargo build command
    let output = Command::new("cargo")
        .args([
            "build",
            "-p",
            "tools",
            "--bins",
            "-Z",
            "unstable-options",
            "--artifact-dir",
            artifact_dir.to_str().unwrap(),
            "--release",
            "--locked",
        ])
        .output()
        .expect("Failed to execute cargo build");

    if !output.status.success() {
        eprintln!(
            "cargo build failed with stderr:\n{}",
            String::from_utf8_lossy(&output.stderr)
        );
        panic!("Cargo build failed");
    }

    // Remove debugging files
    remove_files_with_extension(&artifact_dir, "pdb");
    remove_files_with_extension(&artifact_dir, "dwarf");
}

fn remove_files_with_extension(dir: &Path, ext: &str) {
    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().is_some_and(|e| e == ext) {
                let _ = fs::remove_file(path); // Ignore errors
            }
        }
    }
}
