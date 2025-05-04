fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::configure()
        .out_dir("src")
        .build_client(true)
        .build_server(false)
        .type_attribute(".", "#[derive(serde::Serialize,serde::Deserialize)]")
        .compile_protos(&["proto/tei.proto"], &["proto"])
        .map_err(|e| e.into())
}
