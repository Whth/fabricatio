use clap::Parser;
use deck_loader::loader::AnkiDeckLoader as CoreAnkiDeckLoader;
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
enum Cli {
    /// Build an Anki deck from a project directory
    Build {
        /// Path to the project directory
        project_path: PathBuf,

        /// Output file path for the generated .apkg file
        #[arg(short, long)]
        output: Option<PathBuf>,
    },

    /// Create a new project template
    New {
        /// Path where the new project should be created
        project_path: PathBuf,

        /// Optional name for the deck
        #[arg(short, long)]
        name: Option<String>,

        /// Optional description for the deck
        #[arg(short, long)]
        description: Option<String>,

        /// Optional author for the deck
        #[arg(short, long)]
        author: Option<String>,

        /// Optional name for the model
        #[arg(short, long)]
        model_name: Option<String>,

        /// Optional fields for the model
        #[arg(short, long, num_args = 1..)]
        fields: Vec<String>,
    },

    /// Validate a project directory without building
    Validate {
        /// Path to the project directory
        project_path: PathBuf,
    },
}

fn main() -> Result<(), String> {
    let cli = Cli::parse();

    match cli {
        Cli::Build { project_path, output } => {
            let loader = CoreAnkiDeckLoader::new(project_path.to_string_lossy().to_string())
                .map_err(|e| format!("Failed to create loader: {}", e))?;

            let output_path = output.unwrap_or_else(|| {
                let mut path = project_path.clone();
                path.push("output.apkg");
                path
            });

            loader.build_deck()
                .map_err(|e| format!("Failed to build deck: {}", e))?;

            println!("Deck built successfully. Exporting to {}...", output_path.display());

            loader.export_deck(output_path.to_string_lossy().to_string())
                .map_err(|e| format!("Failed to export deck: {}", e))?;

            println!("Deck exported successfully!");
        }

        Cli::New { project_path, name, description, author, model_name, fields } => {
            CoreAnkiDeckLoader::create_project_template(
                project_path.to_string_lossy().to_string(),
                name,
                description,
                author,
                model_name,
                if fields.is_empty() { None } else { Some(fields) },
            ).map_err(|e| format!("Failed to create project template: {}", e))?;

            println!("Project template created successfully at {}", project_path.display());
        }

        Cli::Validate { project_path } => {
            let loader = CoreAnkiDeckLoader::new(project_path.to_string_lossy().to_string())
                .map_err(|e| format!("Failed to create loader: {}", e))?;

            loader.build_deck()
                .map_err(|e| format!("Validation failed: {}", e))?;

            println!("Project directory is valid!");
        }
    }

    Ok(())
}