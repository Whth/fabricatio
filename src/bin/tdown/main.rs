mod download;
use clap::{Parser, Subcommand};
use colored::*;
use fabricatio_constants::{ROAMING, TEMPLATES};
use flate2::read::GzDecoder;
use reqwest::blocking::Client;
use std::fs::{self, File};
use std::io::{self, Write};
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

        /// Keep the downloaded archive file after extraction
        #[arg(short, long)]
        keep_archive: bool,

        /// Download a specific release version (default: latest)
        #[arg(short, long)]
        version: Option<String>,

        /// Skip extraction and only download the archive
        #[arg(long)]
        download_only: bool,
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
        filter: Option<String>,
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
    #[command(alias = "info")]
    Info {
        /// Show information about a specific version
        #[arg(short, long)]
        version: Option<String>,

        /// Show all available releases
        #[arg(short, long)]
        all: bool,
    },

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

fn retrieve_release(
    client: &Client,
    version: Option<&str>,
) -> Result<serde_json::Value, Box<dyn std::error::Error>> {
    let repo_url = match version {
        Some(v) => format!(
            "https://api.github.com/repos/Whth/fabricatio/releases/tags/{}",
            v
        ),
        None => "https://api.github.com/repos/Whth/fabricatio/releases/latest".to_string(),
    };

    let response = client
        .get(&repo_url)
        .header("User-Agent", "fabricatio_template_downloader")
        .send()?;

    if !response.status().is_success() {
        return Err(format!("Failed to fetch release information: {}", response.status()).into());
    }

    Ok(response.json()?)
}

fn retrieve_all_releases(
    client: &Client,
) -> Result<Vec<serde_json::Value>, Box<dyn std::error::Error>> {
    let repo_url = "https://api.github.com/repos/Whth/fabricatio/releases";
    let response = client
        .get(repo_url)
        .header("User-Agent", "fabricatio_template_downloader")
        .send()?;

    if !response.status().is_success() {
        return Err(format!("Failed to fetch releases: {}", response.status()).into());
    }

    Ok(response.json()?)
}

fn extract_release(
    tar_gz_path: &PathBuf,
    output_dir: &PathBuf,
    verbose: bool,
) -> Result<(), Box<dyn std::error::Error>> {
    if verbose {
        println!(
            "{} Extracting to {}",
            "Extracting".blue(),
            output_dir.display()
        );
    }

    let tar_gz = File::open(tar_gz_path)?;
    let decoder = GzDecoder::new(tar_gz);
    let mut archive = Archive::new(decoder);
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
) -> Result<Vec<(PathBuf, String)>, Box<dyn std::error::Error>> {
    let mut templates = Vec::new();

    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();

        if path.is_dir() {
            // Recursively scan subdirectories
            let mut sub_templates = collect_templates_recursive(&path, filter, base_dir)?;
            templates.append(&mut sub_templates);
        } else if path.is_file() && path.extension().map_or(false, |ext| ext == "hbs") {
            // Get relative path from base directory for display
            let relative_path = path
                .strip_prefix(base_dir)
                .unwrap_or(&path)
                .to_string_lossy()
                .to_string();

            if filter.map_or(true, |f| relative_path.contains(f)) {
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
) -> Result<(), Box<dyn std::error::Error>> {
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

fn confirm_removal(relative_path: &str) -> Result<bool, Box<dyn std::error::Error>> {
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
) -> Result<(), Box<dyn std::error::Error>> {
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
) -> Result<(), Box<dyn std::error::Error>> {
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

fn show_release_info(
    client: &Client,
    version: Option<&str>,
    show_all: bool,
    verbose: bool,
) -> Result<(), Box<dyn std::error::Error>> {
    if show_all {
        let releases = retrieve_all_releases(client)?;
        println!("{} Available releases:", "Releases".green().bold());

        for release in releases.iter().take(10) {
            let tag = release["tag_name"].as_str().unwrap_or("unknown");
            let name = release["name"].as_str().unwrap_or("Unnamed");
            let published = release["published_at"].as_str().unwrap_or("unknown");

            println!("  {} {} - {} ({})", "→".cyan(), tag, name, published);
        }

        if releases.len() > 10 {
            println!(
                "  {} ... and {} more releases",
                "ℹ".blue(),
                releases.len() - 10
            );
        }
    } else {
        let release = retrieve_release(client, version)?;
        let tag = release["tag_name"].as_str().unwrap_or("unknown");
        let name = release["name"].as_str().unwrap_or("Unnamed");
        let published = release["published_at"].as_str().unwrap_or("unknown");
        let body = release["body"].as_str().unwrap_or("No description");

        println!("{} Release Information:", "Release".green().bold());
        println!("  {} Version: {}", "→".cyan(), tag);
        println!("  {} Name: {}", "→".cyan(), name);
        println!("  {} Published: {}", "→".cyan(), published);

        if verbose {
            println!("  {} Description:", "→".cyan());
            for line in body.lines().take(10) {
                println!("    {}", line);
            }
        }

        if let Some(assets) = release["assets"].as_array() {
            println!("  {} Assets:", "→".cyan());
            assets.iter().for_each(|asset| {
                let asset_name = asset["name"].as_str().unwrap_or("unknown");
                let size = asset["size"].as_u64().unwrap_or(0);
                println!("    {} {} ({} bytes)", "→".cyan(), asset_name, size);
            });
        }
    }

    Ok(())
}

fn create_backup(template_dir: &PathBuf, verbose: bool) -> Result<(), Box<dyn std::error::Error>> {
    let backup_dir = template_dir.join("backup");
    fs::create_dir_all(&backup_dir)?;

    if verbose {
        println!("{} Creating backup...", "Backup".yellow());
    }

    if template_dir.exists() {
        for entry in fs::read_dir(template_dir)? {
            let entry = entry?;
            let path = entry.path();
            if path.is_file() && path.extension().map_or(false, |ext| ext == "hbs") {
                let backup_path = backup_dir.join(entry.file_name());
                fs::copy(&path, &backup_path)?;
            }
        }
    }

    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cli = Cli::parse();
    let client = Client::new();

    match &cli.command {
        Commands::Download {
            output_dir,
            keep_archive,
            version,
            download_only,
        } => download::handle_download(
            &client,
            output_dir,
            keep_archive,
            version.as_deref(),
            *download_only,
            cli.verbose,
        )?,

        Commands::List {
            template_dir,
            detailed,
            filter,
        } => list_templates(template_dir, *detailed, filter.as_deref())?,

        Commands::Remove {
            templates,
            template_dir,
        } => remove_templates(templates, template_dir, cli.force, cli.verbose)?,

        Commands::Info { version, all } => {
            show_release_info(&client, version.as_deref(), *all, cli.verbose)?
        }

        Commands::Update {
            template_dir,
            backup,
        } => download::handle_update(&client, template_dir, *backup, cli.verbose)?,
    }

    Ok(())
}
