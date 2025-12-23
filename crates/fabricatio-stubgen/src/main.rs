use pyo3_stub_gen::Result;

fn main() -> Result<()> {
    fabricatio_core::stub_info()?.generate()?;
    fabricatio_memory::stub_info()?.generate()?;
    fabricatio_diff::stub_info()?.generate()?;
    Ok(())
}
