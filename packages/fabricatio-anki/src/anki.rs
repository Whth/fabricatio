use deck_loader::loader::{AnkiDeckLoader, constants};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pythonize::depythonize;

#[cfg(feature = "stubgen")]
use pyo3_stub_gen::derive::*;

use serde_yaml2::wrapper::YamlNodeWrapper;
use std::fs;
use std::path::PathBuf;

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
/// Compile an Anki deck from a project directory and export it to the specified output path.
///
/// This function serves as the main entry point for compiling Anki deck projects created with
/// the fabricatio-anki framework. It takes a project directory containing deck configuration,
/// model definitions, templates, and CSV data, then processes all components to generate a
/// complete Anki deck file (.apkg format).
///
/// The compilation process includes:
/// 1. Loading and validating the deck configuration from deck.toml
/// 2. Processing all model definitions and their associated templates
/// 3. Reading CSV data files and converting them to Anki notes
/// 4. Collecting and packaging media files referenced in the templates
/// 5. Generating the final .apkg file with proper Anki database structure
///
/// Args:
///     path: The absolute or relative path to the Anki deck project directory.
///           This directory should contain:
///           - deck.toml: Main deck configuration file
///           - models/: Directory containing model definitions and templates
///           - data/: Directory containing CSV files with card data
///           - media/: Directory containing any media files (images, audio, etc.)
///
///     output: The absolute or relative path where the compiled .apkg file should be saved.
///             The file will be created if it doesn't exist, or overwritten if it does.
///             The path should include the desired filename with .apkg extension.
///
/// Returns:
///     None on success.
///
/// Raises:
///     Exception: If the project directory structure is invalid or missing required files.
///     Exception: If the deck.toml configuration file contains invalid settings.
///     Exception: If any model definition files are malformed or contain syntax errors.
///     Exception: If CSV data files have mismatched columns compared to model field definitions.
///     Exception: If referenced media files cannot be found or accessed.
///     Exception: If the output path is invalid or cannot be written to due to permissions.
///     Exception: If there are any internal errors during the Anki deck generation process.
///
/// Example:
///     >>> compile_deck("/path/to/my-deck-project", "/path/to/output/my-deck.apkg")
///
/// Note:
///     The function will validate the entire project structure before beginning compilation.
///     All errors are reported with descriptive messages to help identify and fix issues.
///     The generated .apkg file is compatible with Anki 2.1 and later versions.
fn compile_deck(path: PathBuf, output: PathBuf) -> PyResult<()> {
    AnkiDeckLoader::new(path)
        .export_deck(output)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyException, _>(format!("{}", e)))?;
    Ok(())
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
/// Create a new Anki deck project template with the specified configuration.
///
/// This function generates a complete project structure for creating Anki decks using the
/// fabricatio-anki framework. It creates all necessary directories, configuration files,
/// and sample templates to get started with deck development.
///
/// The generated project follows a structured layout that separates concerns:
/// - Deck metadata and global configuration
/// - Model definitions with fields and templates
/// - Data files for card content
/// - Media resources for multimedia content
///
/// Project Structure:
///     anki_deck_project/
///     ├── deck.yaml                # Metadata: Deck name, description, author, etc.
///     ├── models/                  # Each Model corresponds to a subdirectory
///     │   ├── vocab_card/          # Model name
///     │   │   ├── fields.yaml      # Field definitions (e.g., Word, Meaning)
///     │   │   ├── templates/       # Each template corresponds to a subdirectory
///     │   │   │   ├── word_to_meaning/
///     │   │   │   │   ├── front.html
///     │   │   │   │   ├── back.html
///     │   │   │   │   └── style.css
///     │   │   │   └── meaning_to_word/
///     │   │   │       ├── front.html
///     │   │   │       ├── back.html
///     │   │   │       └── style.css
///     │   │   └── media/            # Optional: Media resources specific to this model
///     │   └── grammar_card/
///     │       ├── fields.yaml
///     │       ├── templates/        # Template directory for grammar cards
///     │       └── media/            # Media directory for grammar cards
///     ├── data/                     # User data (for template injection)
///     │   ├── vocab_card.csv        # CSV format, each line represents a card
///     │   └── grammar_card.csv      # CSV data for grammar flashcards
///     └── media/                    # Global media resources (images, audio, etc.)
///
/// Args:
///     path: The absolute or relative path where the new project directory should be created.
///           If the directory doesn't exist, it will be created along with any necessary
///           parent directories. If it already exists, the function will add the project
///           structure to it (existing files may be overwritten).
///
///     deck_name: The display name for the Anki deck that will appear in Anki's deck browser.
///                If None, defaults to "Sample Deck". This name can contain spaces and
///                special characters as it's used for display purposes only.
///
///     deck_description: A detailed description of the deck's purpose and content.
///                       This appears in Anki's deck information and helps users understand
///                       what the deck contains. If None, defaults to "A sample Anki deck
///                       created with Fabricatio".
///
///     author: The name or identifier of the deck creator. This information is embedded in
///             the deck metadata and can be useful for attribution and contact purposes.
///             If None, defaults to "Generated by Fabricatio".
///
///     model_name: The name for the default model (note type) that will be created in the
///                 project. Model names should be descriptive and use underscores instead of
///                 spaces (e.g., "basic_card", "vocabulary_card"). If None, defaults to
///                 "basic_card".
///
///     fields: A list of field names that define the structure of cards using this model.
///             Each field represents a piece of information that can be filled in for each card
///             (e.g., ["Front", "Back"] for basic cards, or ["Word", "Pronunciation",
///             "Definition", "Example"] for vocabulary cards). Field names should be
///             descriptive and avoid special characters. If None, defaults to ["Front",
///             "Back"] for a basic two-sided card model.
///
/// Returns:
///     None on success.
///
/// Raises:
///     Exception: If the specified path cannot be created due to permission restrictions or
///               invalid path format (e.g., contains illegal characters for the filesystem).
///     Exception: If any of the required directories cannot be created in the project structure.
///     Exception: If the configuration files (deck.yaml, fields.yaml) cannot be written due to
///               I/O errors or insufficient disk space.
///     Exception: If the template HTML/CSS files cannot be created or written to.
///     Exception: If the sample CSV data file cannot be generated.
///     Exception: If any parameter contains invalid characters that would cause issues in
///               Anki or the filesystem (e.g., null bytes, extremely long strings).
///
/// Example:
///     Basic project creation:
///     >>> create_deck_project("/path/to/my-new-deck")
///
///     Customized project with specific configuration:
///     >>> create_deck_project(
///     ...     "/path/to/vocabulary-deck",
///     ...     deck_name="French Vocabulary",
///     ...     deck_description="Essential French words for beginners",
///     ...     author="Language Learning Team",
///     ...     model_name="french_vocab",
///     ...     fields=["French", "English", "Pronunciation", "Example"]
///     ... )
///
/// Note:
///     - The function creates a fully functional project template that can be immediately
///       compiled into an Anki deck using the compile_deck function.
///     - Sample data and templates are provided to demonstrate the structure and can be
///       modified or replaced with actual content.
///     - The generated templates include basic HTML structure and CSS styling that can
///       be customized for different visual presentations.
///     - All file paths use forward slashes internally but are converted to the appropriate
///       format for the current operating system.
///     - The project structure is designed to be version-control friendly, with text-based
///       configuration files and clear separation of content and presentation.
fn create_deck_project(
    path: PathBuf,
    deck_name: Option<String>,
    deck_description: Option<String>,
    author: Option<String>,
    model_name: Option<String>,
    fields: Option<Vec<String>>,
) -> PyResult<()> {
    AnkiDeckLoader::create_project_template(
        path,
        deck_name,
        deck_description,
        author,
        model_name,
        fields,
    )
    .map_err(|e| PyErr::new::<pyo3::exceptions::PyException, _>(format!("{}", e)))?;
    Ok(())
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
/// Save metadata as a YAML file in the specified directory.
///
/// This function takes a dictionary of metadata and saves it as a YAML file
/// in the given directory. The file will be named with the provided name
/// and automatically have a .yaml extension added.
///
/// Args:
///     dir_path: The directory path where the YAML file should be saved.
///              The directory must exist and be writable.
///     name: The base name for the YAML file (without extension).
///           The .yaml extension will be automatically appended.
///     data: A dictionary containing the metadata to be serialized to YAML.
///           The dictionary should contain serializable Python objects.
///
/// Returns:
///     None on success.
///
/// Raises:
///     Exception: If the directory path is invalid or not writable.
///     Exception: If the data cannot be serialized to YAML format.
///     Exception: If there are I/O errors during file writing.
///     Exception: If the file cannot be created due to permission issues.
///
/// Example:
///     >>> from pathlib import Path
///     >>> metadata = {"title": "My Deck", "author": "John Doe", "version": "1.0"}
///     >>> save_metadata(Path("/path/to/project"), "deck_info", metadata)
///     # Creates /path/to/project/deck_info.yaml with the metadata
fn save_metadata(dir_path: PathBuf, name: String, data: Bound<'_, PyAny>) -> PyResult<()> {
    fs::create_dir_all(&dir_path)?;
    depythonize::<YamlNodeWrapper>(&data)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))
        .and_then(|value| {
            let content =
                serde_yaml2::to_string(value).map_err(|e| PyRuntimeError::new_err(e.to_string()));
            content.and_then(|content| {
                let path = dir_path.join(format!("{}.yaml", name));
                fs::write(path, content).map_err(|e| PyRuntimeError::new_err(e.to_string()))
            })
        })
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
/// Add CSV data to an Anki deck project by copying a CSV file to the project's data directory.
///
/// This function copies a CSV data file into the appropriate location within an Anki deck project
/// structure. The CSV file will be renamed to match the model name and placed in the project's
/// data directory where it can be used during deck compilation.
///
/// Args:
///     project_path: The path to the root directory of the Anki deck project.
///                   This should contain the standard project structure with a 'data' subdirectory.
///     model_name: The name of the model that this CSV data corresponds to.
///                 The CSV file will be renamed to "{model_name}.csv" in the data directory.
///     data: The path to the source CSV file that contains the card data to be added.
///           This file should have a header row with column names that match the model's fields.
///
/// Returns:
///     None on success.
///
/// Raises:
///     Exception: If the project path does not exist or is not accessible.
///     Exception: If the source CSV file cannot be read or does not exist.
///     Exception: If the data directory cannot be created or written to.
///     Exception: If the file copy operation fails due to I/O errors or permission issues.
///
/// Example:
///     >>> from pathlib import Path
///     >>> add_csv_data(
///     ...     Path("/path/to/my-deck-project"),
///     ...     "vocabulary_cards",
///     ...     Path("/path/to/vocab_data.csv")
///     ... )
///     # Copies vocab_data.csv to /path/to/my-deck-project/data/vocabulary_cards.csv
///
/// Note:
///     - The function will overwrite any existing CSV file with the same model name.
///     - The CSV file should have column headers that match the field names defined in the model.
///     - The data directory will be created if it doesn't exist within the project structure.
fn add_csv_data(project_path: PathBuf, model_name: &str, data: PathBuf) -> PyResult<()> {
    AnkiDeckLoader::new(project_path)
        .add_csv_data(model_name, &data)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))
}

#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
/// Save card type template files (front.html, back.html, and optional style.css) to a directory.
///
/// This function creates the template files that define how cards will be displayed in Anki.
/// It writes the front and back HTML templates, and optionally a CSS stylesheet, to the
/// specified directory. These files are typically used within a model's templates subdirectory
/// to define different card layouts.
///
/// The function writes three potential files:
/// - front.html: Contains the HTML template for the front side of the card
/// - back.html: Contains the HTML template for the back side of the card
/// - style.css: Contains CSS styling rules (only if css parameter is provided)
///
/// Args:
///     dir_path: The directory path where the template files should be saved.
///               This directory must already exist and be writable. Typically this
///               would be a path like "models/model_name/templates/template_name/".
///
///     front: The HTML content for the front side of the card template.
///            This should be valid HTML that can include Anki field placeholders
///            like {{FieldName}} which will be replaced with actual card data.
///            Example: "<div class='front'>{{Question}}</div>"
///
///     back: The HTML content for the back side of the card template.
///           This should be valid HTML and typically includes {{FrontSide}} to
///           show the front content plus additional fields for the answer.
///           Example: "{{FrontSide}}<hr>{{Answer}}"
///
///     css: CSS styling rules to be applied to the card templates.
///          If provided, this will be written to a style.css file.
///          If None, no CSS file will be created. The CSS should be
///          valid stylesheet content that styles the HTML elements
///          in the front and back templates.
///
/// Returns:
///     None on success.
///
/// Raises:
///     Exception: If the directory path does not exist or is not accessible.
///     Exception: If any of the template files cannot be written due to permission issues.
///     Exception: If there are I/O errors during file writing operations.
///     Exception: If the directory path is invalid or points to a file instead of a directory.
///
/// Example:
///     Basic card template creation:
///     >>> from pathlib import Path
///     >>> save_template(
///     ...     Path("/path/to/models/basic/templates/card"),
///     ...     front="<div class='question'>{{Front}}</div>",
///     ...     back="{{FrontSide}}<hr><div class='answer'>{{Back}}</div>"
///     ... )
///
///     Card template with custom CSS styling:
///     >>> save_template(
///     ...     Path("/path/to/models/vocab/templates/word_card"),
///     ...     front="<h2>{{Word}}</h2><p>{{Context}}</p>",
///     ...     back="{{FrontSide}}<hr><div class='definition'>{{Definition}}</div>",
///     ...     css=".question { font-size: 24px; color: blue; } .answer { background: #f0f0f0; }"
///     ... )
///
/// Note:
///     - The directory must exist before calling this function - it will not be created automatically.
///     - Existing template files in the directory will be overwritten without warning.
///     - The HTML content should be properly escaped if it contains special characters.
///     - Field placeholders in the format {{FieldName}} will be replaced by Anki with actual card data.
///     - The CSS file is optional but recommended for consistent card styling across different devices.
///     - Template files use standard HTML/CSS which allows for rich formatting and multimedia content.
#[pyo3(signature=(dir_path, front, back, css=None))]
fn save_template(
    dir_path: PathBuf,
    front: String,
    back: String,
    css: Option<String>,
) -> PyResult<()> {
    fs::create_dir_all(&dir_path)?;
    fs::write(dir_path.join(constants::TEMPLATE_FRONT), front)?;
    fs::write(dir_path.join(constants::TEMPLATE_BACK), back)?;
    if let Some(css) = css {
        fs::write(dir_path.join(constants::TEMPLATE_CSS), css)?;
    }

    Ok(())
}

/// Extracts content located within all occurrences of a specified HTML tag.
///
/// Args:
///     html: The HTML content to search within.
///     tag: The name of the HTML tag whose content needs to be extracted.
///
/// Returns:
///     A concatenated string of all contents found between the opening and closing tags.
fn extract_content_by_tag(html: &str, tag: &str) -> String {
    use regex::Regex;

    let pattern = format!(r"(?s)<{tag}[^>]*>(.*?)</{tag}>");
    let regex = Regex::new(&pattern).unwrap();
    regex
        .captures_iter(html)
        .map(|cap| cap.get(1).map_or("", |m| m.as_str()))
        .collect::<Vec<_>>()
        .join("\n")
}

/// Extract HTML components by separating layout, JavaScript, and CSS content.
///
/// This function parses an HTML string and extracts three distinct components:
/// - Layout HTML (remaining HTML after removing script and style tags)
/// - JavaScript content from <script> tags
/// - CSS content from <style> tags
///
/// Args:
///     html: The HTML string to parse and extract components from.
///
/// Returns:
///     A tuple containing (layout_html, javascript_content, css_content):
///     - layout_html: HTML content with script and style tags removed
///     - javascript_content: Combined JavaScript code from all script tags
///     - css_content: Combined CSS code from all style tags
///
/// Example:
///     >>> html = '<div>Hello</div><script>alert("hi")</script><style>div{color:red}</style>'
///     >>> layout, js, css = extract_html_component(html)
///     >>> print(layout)  # '<div>Hello</div>'
///     >>> print(js)      # 'alert("hi")'
///     >>> print(css)     # 'div{color:red}'
#[cfg_attr(feature = "stubgen", gen_stub_pyfunction)]
#[pyfunction]
fn extract_html_component(html: &str) -> PyResult<(String, String, String)> {
    use regex::Regex;

    // Extract JavaScript from <script> tags
    let js_content = extract_content_by_tag(html, "script");

    // Extract CSS from <style> tags
    let css_content = extract_content_by_tag(html, "style");

    // Remove script and style tags to get remaining HTML layout
    let script_regex = Regex::new(r"(?s)<script[^>]*>.*?</script>").unwrap();
    let style_regex = Regex::new(r"(?s)<style[^>]*>.*?</style>").unwrap();
    let mut layout = script_regex.replace_all(html, "").to_string();
    layout = style_regex.replace_all(&layout, "").to_string();

    Ok((layout, js_content, css_content))
}

/// Registers the Anki deck functions with the Python module.
///
/// Args:
///     _: The Python interpreter instance.
///     m: The Python module to register with.
///
/// Returns:
///     PyResult<()> indicating success.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compile_deck, m)?)?;
    m.add_function(wrap_pyfunction!(create_deck_project, m)?)?;
    m.add_function(wrap_pyfunction!(save_metadata, m)?)?;
    m.add_function(wrap_pyfunction!(save_template, m)?)?;
    m.add_function(wrap_pyfunction!(add_csv_data, m)?)?;
    m.add_function(wrap_pyfunction!(extract_html_component, m)?)?;
    Ok(())
}
