fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::configure()
        .out_dir("src")
        .build_client(true)
        .build_server(false)
        .compile_protos(&["proto/tei.proto"], &["proto"])
        .map_err(|e| e.into())
}