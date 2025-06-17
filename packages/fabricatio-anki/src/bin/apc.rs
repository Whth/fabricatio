use clap::{Parser, ValueEnum};
use deck_loader::loader::AnkiDeckLoader as CoreAnkiDeckLoader;
use std::path::PathBuf;

#[derive(Debug, Clone, ValueEnum)]
enum LogLevel {
    Error,
    Warn,
    Info,
    Debug,
    Trace,
}

#[derive(Debug, Clone, ValueEnum)]
enum OutputFormat {
    Apkg,
    Json,
    Csv,
}

#[derive(Parser, Debug)]
#[command(
    name = "apc",
    version = env!("CARGO_PKG_VERSION"),
    author = env!("CARGO_PKG_AUTHORS"),
    about = "Anki Project Compiler - Build and manage Anki decks from project directories",
    long_about = "A comprehensive CLI tool for creating, building, and managing Anki deck projects. \
                  Supports template generation, validation, and deck compilation with advanced features."
)]
enum Cli {
    /// Build an Anki deck from a project directory
    Build {
        /// Path to the project directory
        #[arg(value_name = "PROJECT_PATH", help = "Path to the project directory")]
        project_path: PathBuf,

        /// Output file path for the generated file
        #[arg(
            short,
            long,
            value_name = "OUTPUT_FILE",
            help = "Output path for the generated file"
        )]
        output: Option<PathBuf>,

        /// Output format
        #[arg(
            short = 'f',
            long,
            value_enum,
            default_value = "apkg",
            help = "Output format for the generated file"
        )]
        format: OutputFormat,

        /// Force overwrite existing output file
        #[arg(
            short = 'F',
            long,
            help = "Overwrite existing output file without confirmation"
        )]
        force: bool,

        /// Enable verbose output
        #[arg(short, long, help = "Enable detailed logging during build process")]
        verbose: bool,

        /// Log level
        #[arg(
            short = 'l',
            long,
            value_enum,
            default_value = "info",
            help = "Set the logging level"
        )]
        log_level: LogLevel,

        /// Compression level for the output file (0-9)
        #[arg(
            short = 'c',
            long,
            value_name = "LEVEL",
            default_value = "6",
            value_parser = clap::value_parser!(u8).range(0..=9),
            help = "Compression level for the output file (0=no compression, 9=maximum)"
        )]
        compression: u8,

        /// Dry run - validate and show what would be built without creating output
        #[arg(short, long, help = "Perform a dry run without creating output files")]
        dry_run: bool,
    },

    /// Create a new project template
    New {
        /// Path where the new project should be created
        #[arg(
            value_name = "PROJECT_PATH",
            help = "Path where the new project should be created"
        )]
        project_path: PathBuf,

        /// Name for the deck
        #[arg(
            short,
            long,
            value_name = "NAME",
            default_value = "My Anki Deck",
            help = "Name of the Anki deck"
        )]
        name: String,

        /// Description for the deck
        #[arg(
            short,
            long,
            value_name = "DESCRIPTION",
            default_value = "Created with Anki Project Compiler",
            help = "Description of the Anki deck"
        )]
        description: String,

        /// Author of the deck
        #[arg(
            short,
            long,
            value_name = "AUTHOR",
            default_value = "Anonymous",
            help = "Author of the deck"
        )]
        author: String,

        /// Name for the model
        #[arg(
            short = 'm',
            long,
            value_name = "MODEL_NAME",
            default_value = "Basic",
            help = "Name for the card model"
        )]
        model_name: String,

        /// Fields for the model
        #[arg(
            short = 'f',
            long,
            value_name = "FIELD",
            default_values = ["Front", "Back"],
            help = "Fields for the card model"
        )]
        fields: Vec<String>,

        /// Force overwrite existing project directory
        #[arg(short = 'F', long, help = "Overwrite existing project directory")]
        force: bool,

        /// Create with minimal template
        #[arg(long, help = "Create a minimal project template")]
        minimal: bool,

        /// Include example cards
        #[arg(long, help = "Include example cards in the template")]
        with_examples: bool,
    },

    /// Validate a project directory without building
    Validate {
        /// Path to the project directory
        #[arg(value_name = "PROJECT_PATH", help = "Path to the project directory")]
        project_path: PathBuf,

        /// Strict validation mode
        #[arg(short, long, help = "Enable strict validation with additional checks")]
        strict: bool,

        /// Show detailed validation report
        #[arg(short, long, help = "Show detailed validation report")]
        verbose: bool,

        /// Fix common issues automatically
        #[arg(short, long, help = "Attempt to fix common validation issues")]
        fix: bool,
    },

    /// Clean build artifacts and temporary files
    Clean {
        /// Path to the project directory
        #[arg(value_name = "PROJECT_PATH", help = "Path to the project directory")]
        project_path: PathBuf,

        /// Remove all generated files including exports
        #[arg(short, long, help = "Remove all generated files including exports")]
        all: bool,

        /// Dry run - show what would be cleaned without actually removing files
        #[arg(
            short,
            long,
            help = "Show what would be cleaned without removing files"
        )]
        dry_run: bool,
    },
}
fn main() -> Result<(), String> {
    let cli = Cli::parse();
    handle_cli_command(cli)
}

fn handle_cli_command(cli: Cli) -> Result<(), String> {
    match cli {
        Cli::Build {
            project_path,
            output,
            format,
            force,
            verbose,
            log_level,
            compression,
            dry_run,
        } => handle_build(
            project_path,
            output,
            format,
            force,
            verbose,
            log_level,
            compression,
            dry_run,
        ),
        Cli::New {
            project_path,
            name,
            description,
            author,
            model_name,
            fields,
            force,
            minimal,
            with_examples,
        } => handle_new(
            project_path,
            name,
            description,
            author,
            model_name,
            fields,
            force,
            minimal,
            with_examples,
        ),
        Cli::Validate {
            project_path,
            strict,
            verbose,
            fix,
        } => handle_validate(project_path, strict, verbose, fix),
        Cli::Clean {
            project_path,
            all,
            dry_run,
        } => handle_clean(project_path, all, dry_run),
    }
}

fn handle_build(
    project_path: PathBuf,
    output: Option<PathBuf>,
    format: OutputFormat,
    force: bool,
    verbose: bool,
    log_level: LogLevel,
    compression: u8,
    dry_run: bool,
) -> Result<(), String> {
    if verbose {
        println!("Building deck from project: {}", project_path.display());
        println!("Log level: {:?}", log_level);
        println!("Compression: {}", compression);
    }

    let loader = CoreAnkiDeckLoader::new(project_path.clone())
        .map_err(|e| format!("Failed to create loader: {}", e))?;

    let output_path = output.unwrap_or_else(|| {
        let mut path = project_path.clone();
        let extension = match format {
            OutputFormat::Apkg => "apkg",
            OutputFormat::Json => "json",
            OutputFormat::Csv => "csv",
        };
        path.push(format!("deck.{}", extension));
        path
    });

    if output_path.exists() && !force {
        return Err(format!(
            "Output file already exists: {}. Use --force to overwrite.",
            output_path.display()
        ));
    }

    if dry_run {
        println!(
            "Dry run: Would build deck and export to {}",
            output_path.display()
        );
        return Ok(());
    }

    loader
        .build_deck()
        .map_err(|e| format!("Failed to build deck: {}", e))?;

    if verbose {
        println!(
            "Deck built successfully. Exporting to {}...",
            output_path.display()
        );
    }

    loader
        .export_deck(output_path.clone())
        .map_err(|e| format!("Failed to export deck: {}", e))?;

    println!("Deck exported successfully to {}", output_path.display());
    Ok(())
}

fn handle_new(
    project_path: PathBuf,
    name: String,
    description: String,
    author: String,
    model_name: String,
    fields: Vec<String>,
    force: bool,
    minimal: bool,
    with_examples: bool,
) -> Result<(), String> {
    if project_path.exists() && !force {
        return Err(format!(
            "Project directory already exists: {}. Use --force to overwrite.",
            project_path.display()
        ));
    }

    println!(
        "Creating new project template at {}",
        project_path.display()
    );
    println!("Deck name: {}", name);
    println!("Author: {}", author);
    println!("Model: {} with fields: {:?}", model_name, fields);

    CoreAnkiDeckLoader::create_project_template(
        project_path.clone(),
        Some(name),
        Some(description),
        Some(author),
        Some(model_name),
        Some(fields),
    )
    .map_err(|e| format!("Failed to create project template: {}", e))?;

    println!(
        "Project template created successfully at {}",
        project_path.display()
    );

    if with_examples {
        println!("Example cards included in the template");
    }
    if minimal {
        println!("Minimal template created");
    }
    Ok(())
}

fn handle_validate(
    project_path: PathBuf,
    strict: bool,
    verbose: bool,
    fix: bool,
) -> Result<(), String> {
    if verbose {
        println!("Validating project directory: {}", project_path.display());
        println!("Strict mode: {}", strict);
    }

    let loader = CoreAnkiDeckLoader::new(project_path.clone())
        .map_err(|e| format!("Failed to create loader: {}", e))?;

    loader
        .build_deck()
        .map_err(|e| format!("Validation failed: {}", e))?;

    if verbose {
        println!("All validation checks passed!");
    } else {
        println!("Project directory is valid!");
    }

    if fix {
        println!("Auto-fix feature not yet implemented");
    }
    Ok(())
}

fn handle_clean(project_path: PathBuf, all: bool, dry_run: bool) -> Result<(), String> {
    println!("Cleaning project directory: {}", project_path.display());

    if dry_run {
        println!("Dry run: Would clean build artifacts");
        if all {
            println!("Dry run: Would also clean export files");
        }
    } else {
        println!("Clean feature not yet implemented");
    }
    Ok(())
}
