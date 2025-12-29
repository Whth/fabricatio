// build.rs
// This build script runs before Rust compilation.
// It builds the frontend SPA (Vue + Vite) using pnpm,
// so that the Rust backend can embed or serve the static assets.

use std::path::Path;
use std::process::Command;

fn main() {
    // Re-run this build script if any frontend source files change.
    // This ensures the frontend is automatically rebuilt when needed.
    println!("cargo:rerun-if-changed=frontend/src");
    println!("cargo:rerun-if-changed=frontend/package.json");
    println!("cargo:rerun-if-changed=frontend/pnpm-lock.yaml");
    println!("cargo:rerun-if-changed=frontend/vite.config.ts");

    let frontend_dir = Path::new("frontend");

    // Verify that the frontend directory exists.
    if !frontend_dir.exists() {
        panic!("Frontend directory not found: {:?}", frontend_dir);
    }

    // Locate the `pnpm` executable in PATH using the `which` crate.
    // This handles platform differences (e.g., `pnpm.cmd` on Windows).
    let pnpm = which::which("pnpm").expect(
        "Failed to find `pnpm` in PATH. \
         Please install pnpm: https://pnpm.io/installation",
    );

    // Install frontend dependencies (idempotent; safe to run even if node_modules exists).
    println!("Running 'pnpm install' in {:?}", frontend_dir);
    let status = Command::new(&pnpm)
        .current_dir(frontend_dir)
        .arg("install")
        .status()
        .expect("Failed to spawn 'pnpm install' process");

    if !status.success() {
        panic!("'pnpm install' exited with a non-zero status");
    }

    // Build the production-ready SPA.
    println!("Running 'pnpm build' in {:?}", frontend_dir);
    let status = Command::new(&pnpm)
        .current_dir(frontend_dir)
        .arg("build")
        .status()
        .expect("Failed to spawn 'pnpm build' process");

    if !status.success() {
        panic!("'pnpm build' exited with a non-zero status");
    }
}