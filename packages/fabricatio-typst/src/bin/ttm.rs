use clap::{Parser, Subcommand};
use std::fs;
use std::path::PathBuf;
use tex_convertor::convert_all_tex_math;
use tex2typst_rs::tex2typst;
// WrapperType enum removed as per instructions

#[derive(Debug, Subcommand)]
enum Commands {
    /// Convert TeX math (e.g., $...$, $$...$$, \(...\), \[...\]) in a file to Typst's $ format
    #[command(alias = "f")] // Shorter alias
    File {
        input: PathBuf,
        #[arg(short, long)]
        output: Option<PathBuf>,
    },
    /// Convert TeX math (e.g., $...$, $$...$$, \(...\), \[...\]) in a string to Typst's $ format
    #[command(alias = "s")] // Shorter alias
    String {
        input_str: String,
        #[arg(short, long)]
        output: Option<PathBuf>,
    },
    /// Directly convert raw LaTeX code to Typst Math code (no wrapper detection)
    #[command(alias = "r")] // Shorter alias
    Raw {
        input_str: String,
        #[arg(short, long)]
        output: Option<PathBuf>,
    },
}

#[derive(Parser, Debug)]
#[command(
    author,
    version,
    about = "Convert TeX math expressions (various delimiters) to Typst format (using $ delimiters).",
    long_about = "This tool converts TeX math expressions, supporting $, $$, \\(, and \\[, \ninto Typst's standard $ delimiter format. Raw TeX code can also be converted directly."
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

// Simplified process_file function
fn process_file(input: PathBuf, output: Option<PathBuf>) -> Result<(), Box<dyn std::error::Error>> {
    let content = fs::read_to_string(&input)
        .map_err(|e| format!("Failed to read file {:?}: {}", input, e))?;
    let processed = convert_all_tex_math(&content)?;
    match output {
        Some(path) => fs::write(&path, processed)
            .map_err(|e| format!("Failed to write to file {:?}: {}", path, e))?,
        None => println!("{}", processed),
    }
    Ok(())
}

// Simplified process_string function
fn process_string(
    input_str: String,
    output: Option<PathBuf>,
) -> Result<(), Box<dyn std::error::Error>> {
    let processed = convert_all_tex_math(&input_str)?;
    match output {
        Some(path) => fs::write(&path, processed)
            .map_err(|e| format!("Failed to write to file {:?}: {}", path, e))?,
        None => println!("{}", processed),
    }
    Ok(())
}

// process_raw_latex remains largely the same, handling content without wrappers
fn process_raw_latex(
    input_str: String,
    output: Option<PathBuf>,
) -> Result<(), Box<dyn std::error::Error>> {
    let converted = tex2typst(&input_str)
        .map_err(|e| format!("Failed to convert raw LaTeX code to Typst Math code: {}", e))?;
    println!(
        "[DEBUG] Converting Raw TeX: \n{}\n  ==> Typst Math (raw):\n{}",
        input_str,
        converted.trim()
    );
    match output {
        Some(path) => fs::write(path, &converted)
            .map_err(|e| format!("Failed to write to file: {}", e).into()),
        None => {
            println!("{}", converted);
            Ok(())
        }
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();

    match cli.command {
        Commands::File { input, output } => process_file(input, output),
        Commands::String { input_str, output } => process_string(input_str, output),
        Commands::Raw { input_str, output } => process_raw_latex(input_str, output),
    }
}
