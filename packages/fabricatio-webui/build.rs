// build.rs
// This build script runs before Rust compilation.
// It builds the frontend SPA (Vue + Vite) using pnpm,
// so that the Rust backend can embed or serve the static assets.

use std::path::Path;
use std::process::Command;

fn main() {
    // Tell Cargo to re-run this script if frontend source files change.
    // This ensures the frontend is rebuilt when needed.
    println!("cargo:rerun-if-changed=frontend/src");
    println!("cargo:rerun-if-changed=frontend/package.json");
    println!("cargo:rerun-if-changed=frontend/pnpm-lock.yaml");
    println!("cargo:rerun-if-changed=frontend/vite.config.ts");

    let frontend_dir = Path::new("frontend");

    // Check if frontend directory exists
    if !frontend_dir.exists() {
        panic!("Frontend directory not found: {:?}", frontend_dir);
    }

    // Check if pnpm is available
    if Command::new("pnpm").arg("--version").output().is_err() {
        panic!("pnpm is not installed. Please install it: https://pnpm.io/installation");
    }

    // Install dependencies (safe to run even if node_modules exists)
    println!("Running 'pnpm install' in {:?}", frontend_dir);
    let status = Command::new("pnpm")
        .current_dir(frontend_dir)
        .arg("install")
        .status()
        .expect("Failed to execute 'pnpm install'");

    if !status.success() {
        panic!("'pnpm install' failed");
    }

    // Build the SPA
    println!("Running 'pnpm build' in {:?}", frontend_dir);
    let status = Command::new("pnpm")
        .current_dir(frontend_dir)
        .arg("build")
        .status()
        .expect("Failed to execute 'pnpm build'");

    if !status.success() {
        panic!("'pnpm build' failed");
    }

    println!(
        "✅ Frontend built successfully. Output: {:?}",
        frontend_dir.join("dist")
    );
}
