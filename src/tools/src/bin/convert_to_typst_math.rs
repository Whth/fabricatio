use clap::{Parser, Subcommand};
use regex::Regex;
use std::fs;
use std::path::PathBuf;
use tex2typst_rs::tex2typst;


#[derive(Debug, Subcommand)]
enum Commands {
    /// Convert TeX content from a file
    #[command(alias = "fc")]
    File {
        input: PathBuf,

        /// Output file for converted Typst content
        #[arg(short, long)]
        output: Option<PathBuf>,
    },
    /// Convert TeX content from a string
    #[command(alias = "sc")]
    String {
        /// Input string containing TeX content

        input_str: String,

        /// Output file for converted Typst content
        #[arg(short, long)]
        output: Option<PathBuf>,
    },
    /// Directly convert raw LaTeX code to Typst Math code
    #[command(alias = "rc")]
    Raw {
        /// Input string containing raw LaTeX code
        input_str: String,

        /// Output file for converted Typst Math content
        #[arg(short, long)]
        output: Option<PathBuf>,
    },
}


#[derive(Parser, Debug)]
#[command(
    author,
    version,
    about = "Convert TeX math expressions to Typst format",
    long_about = None
)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

fn convert_tex_with_pattern(
    pattern: &str,
    string: &str,
    block: bool,
) -> Result<String, Box<dyn std::error::Error>> {
    let re = Regex::new(pattern)?;

    let result = re.replace_all(string, |caps: &regex::Captures| {
        let tex_code = caps.get(1).unwrap().as_str();
        match tex2typst(tex_code) {
            Ok(converted) => {
                if block {
                    format!("$\n{}\n$", converted)
                } else {
                    format!(" ${}$ ", converted)
                }
            }
            Err(e) => {
                if block {
                    format!("$\n{}\n\"{}\"\n$", tex_code.trim(), e)
                } else {
                    format!(" ${}$ ", tex_code)
                }
            }
        }
    });

    Ok(result.into_owned())
}

fn convert_all_inline_tex(string: &str) -> Result<String, Box<dyn std::error::Error>> {
    convert_tex_with_pattern(r"(?s)\\\((.*?)\\\)", string, false)
}

fn convert_all_block_tex(string: &str) -> Result<String, Box<dyn std::error::Error>> {
    convert_tex_with_pattern(r"(?s)\\\[(.*?)\\\]", string, true)
}

fn process_file(input: PathBuf, output: Option<PathBuf>) -> Result<(), Box<dyn std::error::Error>> {
    let content = fs::read_to_string(input)?;

    let processed = convert_all_block_tex(&content)
        .and_then(|block_processed| convert_all_inline_tex(&block_processed))?;

    match output {
        Some(path) => fs::write(path, processed)?,
        None => println!("{}", processed),
    }

    Ok(())
}

fn process_string(input_str: String, output: Option<PathBuf>) -> Result<(), Box<dyn std::error::Error>> {
    let processed = convert_all_block_tex(&input_str)
        .and_then(|block_processed| convert_all_inline_tex(&block_processed))?;

    match output {
        Some(path) => fs::write(path, processed)?,
        None => println!("{}", processed),
    }

    Ok(())
}

fn process_raw_latex(input_str: String, output: Option<PathBuf>) -> Result<(), Box<dyn std::error::Error>> {
    let converted = tex2typst(&input_str)
        .expect("Failed to convert raw LaTeX code to Typst Math code");
    match output {
        Some(path) => fs::write(path, converted).map_err(|_| "Failed to write to file".into()),
        None => Ok(println!("{}", converted)),
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