mod download;
mod error;
mod releases;
mod repo;

use clap::{Parser, Subcommand};
use colored::*;
use fabricatio_constants::{ROAMING, TEMPLATES};
use flate2::bufread::GzDecoder;
use reqwest::Client;
use std::fs::{self};
use std::io::{self, BufReader, Write};
use std::path::PathBuf;
use tar::Archive;

/// A full-featured command-line interface for managing Fabricatio templates.
#[derive(Parser)]
#[command(
    name = "fabricatio_template_downloader",
    about = "Manage Fabricatio templates - download, install, and manage template files",
    version,
    author
)]
struct Cli {
    /// Enable verbose output
    #[arg(long, global = true)]
    verbose: bool,

    /// Force operations without confirmation prompts
    #[arg(short, long, global = true)]
    force: bool,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Download and install templates from GitHub releases
    #[command(alias = "dl")]
    Download {
        /// The directory to output the templates to
        #[arg(short, long, default_value = ROAMING.as_os_str())]
        output_dir: PathBuf,

        /// Download a specific release version (default: latest)
        #[arg(short, long)]
        version: Option<String>,
    },

    /// List available templates in the local directory
    #[command(alias = "ls")]
    List {
        /// The directory to list templates from
        #[arg(short, long, default_value = TEMPLATES.as_os_str())]
        template_dir: PathBuf,

        /// Show detailed information about each template
        #[arg(short, long)]
        detailed: bool,

        /// Filter templates by pattern
        #[arg(short, long)]
        pattern: Option<String>,
    },

    /// Remove templates from the local directory
    #[command(alias = "rm")]
    Remove {
        /// Template names to remove
        #[arg(required = true)]
        templates: Vec<String>,

        /// The directory to remove templates from
        #[arg(short, long, default_value = TEMPLATES.as_os_str())]
        template_dir: PathBuf,
    },

    /// Show information about available releases
    Info {},

    /// Update templates to the latest version
    #[command(alias = "up")]
    Update {
        /// The directory containing templates to update
        #[arg(short, long, default_value = ROAMING.as_os_str())]
        template_dir: PathBuf,

        /// Backup existing templates before updating
        #[arg(short, long)]
        backup: bool,
    },
}

pub fn extract_release(
    tar_gz_path: &PathBuf,
    output_dir: &PathBuf,
    verbose: bool,
) -> error::Result<()> {
    if verbose {
        println!(
            "{} Extracting {} to {}",
            "Extracting".blue(),
            tar_gz_path.display(),
            output_dir.display()
        );
    }

    let file = fs::File::open(tar_gz_path)?;

    let decoder = GzDecoder::new(BufReader::new(file));

    let mut archive = Archive::new(decoder);

    fs::create_dir_all(output_dir)?;

    archive.unpack(output_dir)?;

    if verbose {
        println!("{} Extraction completed", "✓".green());
    }

    Ok(())
}
fn collect_templates_recursive(
    dir: &PathBuf,
    filter: Option<&str>,
    base_dir: &PathBuf,
) -> error::Result<Vec<(PathBuf, String)>> {
    let mut templates = Vec::new();

    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();

        if path.is_dir() {
            // Recursively scan subdirectories
            let mut sub_templates = collect_templates_recursive(&path, filter, base_dir)?;
            templates.append(&mut sub_templates);
        } else if path.is_file() && path.extension().is_some_and(|ext| ext == "hbs") {
            // Get relative path from base directory for display
            let relative_path = path
                .strip_prefix(base_dir)
                .unwrap_or(&path)
                .to_string_lossy()
                .to_string();

            if filter.is_none_or(|f| relative_path.contains(f)) {
                templates.push((path, relative_path));
            }
        }
    }

    Ok(templates)
}

fn list_templates(
    template_dir: &PathBuf,
    detailed: bool,
    filter: Option<&str>,
) -> error::Result<()> {
    if !template_dir.exists() {
        println!(
            "{} Template directory does not exist: {}",
            "✗".red(),
            template_dir.display()
        );
        return Ok(());
    }

    let templates = collect_templates_recursive(template_dir, filter, template_dir)?;

    if templates.is_empty() {
        println!("{} No templates found", "ℹ".blue());
        return Ok(());
    }

    // Sort by relative path for consistent ordering
    let mut sorted_templates = templates;
    sorted_templates.sort_by(|a, b| a.1.cmp(&b.1));

    println!(
        "{} Found {} templates:",
        "Templates".green().bold(),
        sorted_templates.len()
    );

    for (path, relative_path) in sorted_templates {
        if detailed {
            let metadata = path.metadata()?;
            let size = metadata.len();
            let modified = metadata
                .modified()?
                .duration_since(std::time::UNIX_EPOCH)?
                .as_secs();

            println!(
                "  {} {} ({} bytes, modified: {})",
                "→".cyan(),
                relative_path,
                size,
                chrono::DateTime::from_timestamp(modified as i64, 0)
                    .map(|dt| dt.format("%Y-%m-%d %H:%M:%S").to_string())
                    .unwrap_or_else(|| "unknown".to_string())
            );
        } else {
            println!("  {} {}", "→".cyan(), relative_path);
        }
    }

    Ok(())
}

fn confirm_removal(relative_path: &str) -> error::Result<bool> {
    print!(
        "{} Remove template '{}'? [y/N]: ",
        "?".yellow(),
        relative_path
    );
    io::stdout().flush()?;

    let mut input = String::new();
    io::stdin().read_line(&mut input)?;

    Ok(input.trim().to_lowercase().starts_with('y'))
}

fn remove_single_template(
    template_path: &PathBuf,
    relative_path: &str,
    force: bool,
    verbose: bool,
) -> error::Result<()> {
    if !force && !confirm_removal(relative_path)? && verbose {
        println!("{} Skipped {}", "→".yellow(), relative_path);
        return Ok(());
    }

    fs::remove_file(template_path)?;

    if verbose {
        println!("{} Removed {}", "✓".green(), relative_path);
    }

    Ok(())
}

fn remove_templates(
    templates: &[String],
    template_dir: &PathBuf,
    force: bool,
    verbose: bool,
) -> error::Result<()> {
    use glob::Pattern;

    templates.iter().try_for_each(|pattern| {
        let pattern = Pattern::new(pattern).map_err(|e| {
            io::Error::new(
                io::ErrorKind::InvalidInput,
                format!("Invalid pattern: {}", e),
            )
        })?;

        let all_templates = collect_templates_recursive(template_dir, None, template_dir)?;
        let matched_templates: Vec<_> = all_templates
            .into_iter()
            .filter(|(_, name)| pattern.matches(name))
            .collect();

        if matched_templates.is_empty() {
            eprintln!("{} No templates matched pattern: {}", "✗".red(), pattern);
            return Ok(());
        }

        matched_templates
            .iter()
            .try_for_each(|(path, name)| remove_single_template(path, name, force, verbose))
    })
}

fn create_backup(template_dir: &PathBuf, verbose: bool) -> error::Result<()> {
    let backup_dir = template_dir.join("backup");
    fs::create_dir_all(&backup_dir)?;

    if verbose {
        println!("{} Creating backup...", "Backup".yellow());
    }

    if template_dir.exists() {
        for entry in fs::read_dir(template_dir)? {
            let entry = entry?;
            let path = entry.path();
            if path.is_file() && path.extension().is_some_and(|ext| ext == "hbs") {
                let backup_path = backup_dir.join(entry.file_name());
                fs::copy(&path, &backup_path)?;
            }
        }
    }

    Ok(())
}

#[tokio::main]
async fn main() -> Result<(), error::Error> {
    let cli = Cli::parse();
    let client = Client::new();

    match &cli.command {
        Commands::Download {
            output_dir,
            version,
        } => {
            download::handle_download(&client, output_dir, version.as_deref(), cli.verbose).await?
        }

        Commands::List {
            template_dir,
            detailed,
            pattern: filter,
        } => list_templates(template_dir, *detailed, filter.as_deref())?,

        Commands::Remove {
            templates,
            template_dir,
        } => remove_templates(templates, template_dir, cli.force, cli.verbose)?,

        Commands::Info {} => {
            releases::show_releases().await?;
        }

        Commands::Update {
            template_dir,
            backup,
        } => download::handle_update(&client, template_dir, *backup, cli.verbose).await?,
    }

    Ok(())
}
