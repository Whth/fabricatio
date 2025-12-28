use crate::error::Result;
/// A better design could be implemented since a deck contains multiple models, each model contains multiple templates,
/// and each template has front/back content and CSS. This can be perfectly represented using a directory structure.
///
/// Users can edit directories and files through tools or automation, then we provide a loader to convert this into a complete
/// deck structure. Finally, according to the user-provided data, the deck's questions are injected and exported.
///
/// Project Structure:
///
/// ```text
/// anki_deck_project/
/// ├── deck.yaml                # Metadata: Deck name, description, author, etc.
/// ├── models/                  # Each Model corresponds to a subdirectory
/// │   ├── vocab_card/          # Model name
/// │   │   ├── fields.yaml      # Field definitions (e.g., Word, Meaning)
/// │   │   ├── templates/       # Each template corresponds to a subdirectory
/// │   │   │   ├── word_to_meaning/
/// │   │   │   │   ├── front.html
/// │   │   │   │   ├── back.html
/// │   │   │   │   └── style.css
/// │   │   │   └── meaning_to_word/
/// │   │   │       ├── front.html
/// │   │   │       ├── back.html
/// │   │   │       └── style.css
/// │   │   └── media/            # Optional: Media resources specific to this model
/// │   └── grammar_card/
/// │       ├── fields.yaml
/// │       ├── templates/
/// │       └── media/
/// ├── data/                     # User data (for template injection)
/// │   ├── vocab_card.csv        # CSV format, each line represents a card
/// │   └── grammar_card.csv
/// └── media/                    # Global media resources (images, audio, etc.)
/// ```
use genanki_rs_rev::{Deck, Field, Model, Note, PackageWriter, Template};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

#[derive(Debug, Serialize, Deserialize)]
pub struct DeckConfig {
    name: String,
    description: String,
    deck_id: i64,
    author: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ModelConfig {
    model_id: i64,
    fields: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct TemplateConfig {
    name: String,
    front_html: String,
    back_html: String,
    style_css: String,
}

#[derive(Debug)]
pub struct ModelData {
    config: ModelConfig,
    templates: Vec<TemplateConfig>,
    media_files: Vec<PathBuf>,
}

pub struct AnkiDeckLoader {
    project_path: PathBuf,
}

pub mod constants {
    pub const MODELS_DIR: &str = "models";
    pub const TEMPLATE_DIR: &str = "templates";
    pub const DATA_DIR: &str = "data";
    pub const MEDIA_DIR: &str = "media";
    pub const DECK_FILE: &str = "deck.yaml";
    pub const FIELDS_FILE: &str = "fields.yaml";
    pub const TEMPLATE_FRONT: &str = "front.html";
    pub const TEMPLATE_BACK: &str = "back.html";
    pub const TEMPLATE_CSS: &str = "style.css";
}
use constants::*;
impl AnkiDeckLoader {
    /// Reads and deserializes a YAML file into the specified type.
    ///
    /// # Arguments
    /// * `file_path` - Path to the YAML file
    /// * `context` - Context description for error messages
    ///
    /// # Returns
    /// * `Result<T, String>` - Deserialized data or error message
    fn read_yaml<T: for<'de> Deserialize<'de>>(&self, file_path: PathBuf) -> Result<T> {
        let content = fs::read_to_string(&file_path)?;
        serde_yaml2::from_str(&content).map_err(Into::into)
    }

    /// Collects all files from a directory (non-recursive, depth 1).
    ///
    /// # Arguments
    /// * `dir_path` - Directory path to scan
    ///
    /// # Returns
    /// * `Vec<PathBuf>` - Vector of file paths found in the directory
    fn collect_files_from_dir<P: AsRef<Path>>(&self, dir_path: P) -> Vec<PathBuf> {
        if !dir_path.as_ref().exists() {
            return Vec::new();
        }

        WalkDir::new(dir_path)
            .min_depth(1)
            .max_depth(1)
            .into_iter()
            .filter_map(|entry| entry.ok())
            .filter(|entry| entry.file_type().is_file())
            .map(|entry| entry.path().to_path_buf())
            .collect::<Vec<_>>()
    }

    /// Gets directory entries from a path using WalkDir.
    ///
    /// # Arguments
    /// * `dir_path` - Directory path to scan
    ///
    /// # Returns
    /// * Iterator over directory entries (directories only, depth 1)
    fn get_directory_entries(&self, dir_path: &Path) -> impl Iterator<Item = walkdir::DirEntry> {
        WalkDir::new(dir_path)
            .min_depth(1)
            .max_depth(1)
            .into_iter()
            .filter_map(|entry| entry.ok())
            .filter(|entry| entry.file_type().is_dir())
    }

    /// Collects directory names from a given path.
    ///
    /// # Arguments
    /// * `dir_path` - Directory path to scan for subdirectories
    ///
    /// # Returns
    /// * `Result<Vec<String>, String>` - Vector of directory names or error message
    fn collect_dir_names(&self, dir_path: &Path) -> Vec<String> {
        if !dir_path.exists() {
            Vec::new()
        } else {
            self.get_directory_entries(dir_path)
                .map(|entry| entry.file_name().to_string_lossy().to_string())
                .collect::<Vec<String>>()
        }
    }

    /// Loads template configurations from the specified templates directory.
    ///
    /// # Arguments
    /// * `templates_path` - Path to the templates directory
    ///
    /// # Returns
    /// * `Vec<TemplateConfig>` - Vector of loaded template configurations
    fn load_templates(&self, templates_path: &Path) -> Vec<TemplateConfig> {
        if !templates_path.exists() {
            return Vec::new();
        }

        self.get_directory_entries(templates_path)
            .map(|entry| {
                let template_name = entry.file_name().to_string_lossy().to_string();
                let template_path = entry.path();

                let front_html =
                    fs::read_to_string(template_path.join(TEMPLATE_FRONT)).unwrap_or_default();
                let back_html =
                    fs::read_to_string(template_path.join(TEMPLATE_BACK)).unwrap_or_default();
                let style_css =
                    fs::read_to_string(template_path.join(TEMPLATE_CSS)).unwrap_or_default();

                TemplateConfig {
                    name: template_name,
                    front_html,
                    back_html,
                    style_css,
                }
            })
            .collect()
    }

    /// Creates a genanki Model from ModelData.
    ///
    /// # Arguments
    /// * `model_name` - Name of the model
    /// * `model_data` - Model data containing configuration and templates
    ///
    /// # Returns
    /// * `Model` - Configured genanki Model instance
    fn create_genanki_model(&self, model_name: &str, model_data: &ModelData) -> Model {
        let model_fields: Vec<Field> = model_data
            .config
            .fields
            .iter()
            .map(|f| Field::new(f))
            .collect();

        let model_templates: Vec<Template> = model_data
            .templates
            .iter()
            .map(|t| {
                Template::new(&t.name)
                    .qfmt(&t.front_html)
                    .afmt(&t.back_html)
            })
            .collect();

        let combined_css = model_data
            .templates
            .iter()
            .map(|t| t.style_css.as_str())
            .collect::<Vec<_>>()
            .join("\n");

        let mut model = Model::new(
            model_data.config.model_id,
            model_name,
            model_fields,
            model_templates,
        );
        if !combined_css.is_empty() {
            model = model.css(combined_css);
        }
        model
    }

    /// Adds notes to a deck from CSV data.
    ///
    /// # Arguments
    /// * `deck` - Mutable reference to the deck
    /// * `model` - Model to use for creating notes
    /// * `csv_data` - CSV data as a vector of string vectors
    fn add_notes_to_deck(&self, deck: &mut Deck, model: Model, csv_data: Vec<Vec<String>>) {
        csv_data
            .into_iter()
            .filter(|row| !row.is_empty())
            .filter_map(|row| {
                let field_refs: Vec<&str> = row.iter().map(|s| s.as_str()).collect();
                Note::new(model.clone(), field_refs).ok()
            })
            .for_each(|note| deck.add_note(note));
    }

    /// Collects all media files (model-specific and global).
    ///
    /// # Arguments
    /// * `model_names` - Slice of model names to collect media files from
    ///
    /// # Returns
    /// * `Result<Vec<String>, String>` - Vector of media file paths or error message
    fn collect_all_media_files(&self, model_names: &[String]) -> Result<Vec<PathBuf>> {
        let mut all_media_files = Vec::new();

        // Collect model-specific media files using iterators
        all_media_files.extend(
            model_names
                .iter()
                .map(|model_name| self.load_model_data(model_name))
                .collect::<Result<Vec<_>>>()?
                .into_iter()
                .flat_map(|model_data| model_data.media_files.into_iter()),
        );

        // Collect global media files using iterators
        let global_media_path = self.project_path.join(MEDIA_DIR);
        all_media_files.extend(self.collect_files_from_dir(&global_media_path));

        Ok(all_media_files)
    }

    /// Builds a complete deck with all models and notes.
    ///
    /// # Returns
    /// * `Result<(Deck, Vec<String>), String>` - Tuple of deck and media files or error message
    fn build_complete_deck(&self) -> Result<(Deck, Vec<PathBuf>)> {
        let deck_config = self.load_deck_config()?;
        let mut deck = Deck::new(
            deck_config.deck_id,
            &deck_config.name,
            &deck_config.description,
        );
        let model_names = self.get_available_models();

        model_names.iter().try_for_each(|model_name| {
            let model_data = self.load_model_data(model_name)?;
            let csv_data = self.load_csv_data(model_name)?;
            let model = self.create_genanki_model(model_name, &model_data);
            self.add_notes_to_deck(&mut deck, model, csv_data);
            Result::<()>::Ok(())
        })?;

        let all_media_files = self.collect_all_media_files(&model_names)?;
        Ok((deck, all_media_files))
    }

    /// Writes deck or package to file.
    ///
    /// # Arguments
    /// * `deck` - Deck to write
    /// * `media_files` - Vector of media file paths
    /// * `output_path` - Output file path
    ///
    /// # Returns
    /// * `Result<()>` - Success or error message
    fn write_deck_to_file<P: AsRef<Path>>(
        &self,
        deck: Deck,
        media_files: Vec<P>,
        output_path: P,
    ) -> Result<()> {
        let mut w = PackageWriter::new();

        media_files.into_iter().try_for_each(|media_file| {
            w.add_media(
                &media_file
                    .as_ref()
                    .strip_prefix(self.project_path.join(MEDIA_DIR))
                    .unwrap()
                    .to_str()
                    .unwrap(),
                media_file.as_ref().clone(),
            )
        })?;
        w.build(vec![deck])?.write_to_file(output_path)?;

        Ok(())
    }

    /// Creates directory structure with error handling.
    ///
    /// # Arguments
    /// * `path` - Base path to create directories in
    ///
    /// # Returns
    /// * `Result<()>` - Success or error message
    fn create_dir_structure(&self, path: &Path) -> Result<()> {
        [MODELS_DIR, DATA_DIR, MEDIA_DIR]
            .iter()
            .try_for_each(|dir| fs::create_dir_all(path.join(dir)))
            .map_err(Into::into)
    }

    /// Writes YAML file with error handling.
    ///
    /// # Arguments
    /// * `path` - File path to write to
    /// * `data` - Data to serialize and write
    /// * `context` - Context description for error messages
    ///
    /// # Returns
    /// * `Result<()>` - Success or error message
    fn write_yaml<T: Serialize>(&self, path: PathBuf, data: &T) -> Result<()> {
        let yaml_content = serde_yaml2::to_string(data)?;
        fs::write(path, yaml_content).map_err(Into::into)
    }

    /// Creates a timestamp for unique ID generation.
    ///
    /// # Returns
    /// * `i64` - Unix timestamp in seconds
    fn create_timestamp() -> i64 {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_else(|_| std::time::Duration::from_secs(0))
            .as_secs() as i64
    }

    /// Creates a new AnkiDeckLoader instance.
    ///
    /// # Arguments
    /// * `project_path` - Path to the Anki deck project directory
    ///
    /// # Returns
    /// * `Result<Self, String>` - New instance or error message
    pub fn new(project_path: PathBuf) -> Self {
        Self { project_path }
    }

    /// Loads deck configuration from deck.yaml file.
    ///
    /// # Returns
    /// * `Result<DeckConfig, String>` - Deck configuration or error message
    pub fn load_deck_config(&self) -> Result<DeckConfig> {
        let deck_config_path = self.project_path.join(DECK_FILE);
        self.read_yaml(deck_config_path)
    }

    /// Loads model data including configuration, templates, and media files.
    ///
    /// # Arguments
    /// * `model_name` - Name of the model to load
    ///
    /// # Returns
    /// * `Result<ModelData, String>` - Model data or error message
    pub fn load_model_data(&self, model_name: &str) -> Result<ModelData> {
        let model_path = self.project_path.join(MODELS_DIR).join(model_name);

        // Load model config
        let fields_path = model_path.join(FIELDS_FILE);
        let config: ModelConfig = self.read_yaml(fields_path)?;

        // Load templates
        let templates_path = model_path.join(TEMPLATE_DIR);
        let templates = self.load_templates(&templates_path);

        // Load media files
        let media_files = self.collect_files_from_dir(&model_path.join(MEDIA_DIR));

        Ok(ModelData {
            config,
            templates,
            media_files,
        })
    }

    /// Gets list of available model names from the models directory.
    ///
    /// # Returns
    /// * `Result<Vec<String>, String>` - Vector of model names or error message
    pub fn get_available_models(&self) -> Vec<String> {
        let models_path = self.project_path.join(MODELS_DIR);
        self.collect_dir_names(&models_path)
    }

    /// Loads CSV data for a specific model.
    ///
    /// # Arguments
    /// * `model_name` - Name of the model to load CSV data for
    ///
    /// # Returns
    /// * `Result<Vec<Vec<String>>, String>` - CSV data as vector of string vectors or error message
    pub fn load_csv_data(&self, model_name: &str) -> Result<Vec<Vec<String>>> {
        let csv_path = self
            .project_path
            .join(DATA_DIR)
            .join(format!("{}.csv", model_name));

        if !csv_path.exists() {
            return Ok(Vec::new());
        }

        let content = fs::read_to_string(&csv_path)?;

        let mut reader = csv::Reader::from_reader(content.as_bytes());
        Ok(reader
            .records()
            .filter_map(|r| r.ok())
            .map(|record| record.iter().map(|s| s.to_string()).collect())
            .collect())
    }

    /// Adds CSV data file to the project for a specific model.
    ///
    /// # Arguments
    /// * `model_name` - Name of the model to add CSV data for
    /// * `data` - Path to the CSV data file to copy
    ///
    /// # Returns
    /// * `Result<()>` - Success or error message
    pub fn add_csv_data(&self, model_name: &str, data: &PathBuf) -> Result<()> {
        let data_dir = self.project_path.join(DATA_DIR);
        fs::create_dir_all(&data_dir)?;

        let target_path = data_dir.join(format!("{}.csv", model_name));

        fs::copy(data, &target_path)?;

        Ok(())
    }

    /// Builds the deck (validation only, does not export).
    ///
    /// # Returns
    /// * `Result<()>` - Success or error message
    pub fn build_deck(&self) -> Result<()> {
        let (_deck, _media_files) = self.build_complete_deck()?;
        Ok(())
    }

    /// Exports the complete deck to an .apkg file.
    ///
    /// # Arguments
    /// * `output_path` - Path where the .apkg file will be saved
    ///
    /// # Returns
    /// * `Result<()>` - Success or error message
    pub fn export_deck<P: AsRef<Path>>(&self, output_path: P) -> Result<()> {
        let (deck, media_files) = self.build_complete_deck()?;
        self.write_deck_to_file(deck, media_files, output_path.as_ref().to_path_buf())
    }

    /// Creates a new Anki deck project template with sample files.
    ///
    /// # Arguments
    /// * `project_path` - Path where the project will be created
    /// * `deck_name` - Optional deck name (defaults to "Sample Deck")
    /// * `deck_description` - Optional deck description
    /// * `author` - Optional author name
    /// * `model_name` - Optional model name (defaults to "basic_card")
    /// * `fields` - Optional field names (defaults to ["Front", "Back"])
    ///
    /// # Returns
    /// * `Result<()>` - Success or error message
    pub fn create_project_template(
        project_path: PathBuf,
        deck_name: Option<String>,
        deck_description: Option<String>,
        author: Option<String>,
        model_name: Option<String>,
        fields: Option<Vec<String>>,
    ) -> Result<()> {
        let loader = Self {
            project_path: project_path.clone(),
        };

        // Create directory structure
        loader.create_dir_structure(&project_path)?;

        // Create sample deck.yaml
        let deck_config = DeckConfig {
            name: deck_name.unwrap_or_else(|| "Sample Deck".to_string()),
            description: deck_description.unwrap_or_else(|| "A sample Anki deck".to_string()),
            deck_id: Self::create_timestamp(),
            author: author.or(Some("Generated by Fabricatio".to_string())),
        };
        loader.write_yaml(project_path.join(DECK_FILE), &deck_config)?;

        // Create sample model
        let model_name = model_name.unwrap_or_else(|| "basic_card".to_string());
        let model_path = project_path.join(MODELS_DIR).join(&model_name);
        fs::create_dir_all(&model_path)?;

        let model_config = ModelConfig {
            model_id: Self::create_timestamp() + 1,
            fields: fields.unwrap_or_else(|| vec!["Front".to_string(), "Back".to_string()]),
        };
        loader.write_yaml(model_path.join(FIELDS_FILE), &model_config)?;

        // Create sample template
        let template_path = model_path.join(TEMPLATE_DIR).join("card");
        fs::create_dir_all(&template_path)?;

        let template_files = [
            (TEMPLATE_FRONT, "{{Front}}"),
            (
                TEMPLATE_BACK,
                "{{FrontSide}}\n\n<hr id=\"answer\">\n\n{{Back}}",
            ),
            (
                TEMPLATE_CSS,
                ".card {\n  font-family: arial;\n  font-size: 20px;\n  text-align: center;\n  color: black;\n  background-color: white;\n}",
            ),
        ];

        template_files
            .iter()
            .try_for_each(|(filename, content)| fs::write(template_path.join(filename), content))?;

        // Create sample CSV data
        fs::write(
            project_path
                .join(DATA_DIR)
                .join(format!("{}.csv", model_name)),
            "Front,Back\n\"What is the capital of France?\",\"Paris\"\n\"What is 2+2?\",\"4\"",
        )?;

        Ok(())
    }
}
