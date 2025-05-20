use std::fs;
use std::path::Path;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::configure()
        .out_dir("src")
        .build_client(true)
        .build_server(false)
        .type_attribute(".", "#[derive(serde::Serialize,serde::Deserialize)]")
        .compile_protos(&["proto/tei.proto"], &["proto"])
        .map(|_| {
            if Path::new("src/tei.v1.rs").exists() {
                fs::rename("src/tei.v1.rs", "src/tei.rs").expect("Failed to rename file")
            }
        })
        .map_err(|e| e.into())
}
