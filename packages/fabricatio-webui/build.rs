use std::env;
use std::path::Path;
use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=frontend/src");
    println!("cargo:rerun-if-changed=frontend/package.json");
    println!("cargo:rerun-if-changed=frontend/pnpm-lock.yaml");
    println!("cargo:rerun-if-changed=frontend/vite.config.ts");

    let frontend_dir = Path::new("frontend");

    if !frontend_dir.exists() {
        panic!("Frontend directory not found: {:?}", frontend_dir);
    }

    // Try to locate pnpm from PNPM_HOME first
    let pnpm = if let Ok(pnpm_home) = env::var("PNPM_HOME") {
        let pnpm_home_path = Path::new(&pnpm_home);
        // Platform-specific executable names
        let candidates = if cfg!(windows) {
            vec!["pnpm.exe", "pnpm.cmd", "pnpm"]
        } else {
            vec!["pnpm"]
        };

        candidates
            .into_iter()
            .map(|name| pnpm_home_path.join(name))
            .find(|p| p.exists())
    } else {
        None
    };

    // Fall back to searching in PATH
    let pnpm = if let Some(pnpm_path) = pnpm {
        pnpm_path
    } else {
        which::which("pnpm").expect(
            "Failed to find `pnpm` in PATH. \
             Please install pnpm: https://pnpm.io/installation",
        )
    };

    // Install frontend dependencies
    println!("Running 'pnpm install' in {:?}", frontend_dir);
    let status = Command::new(&pnpm)
        .current_dir(frontend_dir)
        .arg("install")
        .status()
        .expect("Failed to spawn 'pnpm install' process");

    if !status.success() {
        panic!("'pnpm install' exited with a non-zero status");
    }

    // Build the production-ready SPA
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
