use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

fn main() {
    // 获取 DATA 环境变量，若未设置则使用默认路径 "extra"
    let data_dir: PathBuf = PathBuf::from("extra");

    // 构建目标目录 extra/scripts
    let artifact_dir = data_dir.join("scripts");

    // 如果 scripts 目录已经存在且非空，直接退出
    if artifact_dir.exists() {
        match fs::read_dir(&artifact_dir) {
            Ok(mut entries) => {
                if entries.next().is_some() {
                    println!("Scripts directory is not empty, exiting...");
                    return;
                }
            }
            Err(_) => {
                panic!("Failed to read scripts directory");
            }
        }
    }

    // 创建输出目录
    if let Err(e) = fs::create_dir_all(&artifact_dir) {
        panic!(
            "Failed to create artifact directory {}: {}",
            artifact_dir.display(),
            e
        );
    }

    // 执行 cargo build 命令
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

    // 删除调试文件
    remove_files_with_extension(&artifact_dir, "pdb");
    remove_files_with_extension(&artifact_dir, "dwarf");
}

fn remove_files_with_extension(dir: &Path, ext: &str) {
    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().is_some_and(|e| e == ext) {
                let _ = fs::remove_file(path); // 忽略错误
            }
        }
    }
}
