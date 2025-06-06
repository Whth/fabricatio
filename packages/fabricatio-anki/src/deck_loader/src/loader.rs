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
use genanki_rs::{Deck, Field, Model, Note, Package, Template};
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
    // Helper function to read YAML file and deserialize
    fn read_yaml<T: for<'de> Deserialize<'de>>(
        &self,
        file_path: PathBuf,
        context: &str,
    ) -> Result<T, String> {
        let content = fs::read_to_string(&file_path)
            .map_err(|e| format!("Failed to read {}: {}", context, e))?;

        serde_yml::from_str(&content).map_err(|e| format!("Failed to parse {}: {}", context, e))
    }

    // Helper function to collect files from a directory
    fn collect_files_from_dir(&self, dir_path: &Path) -> Vec<PathBuf> {
        if !dir_path.exists() {
            return Vec::new();
        }

        WalkDir::new(dir_path)
            .min_depth(1)
            .max_depth(1)
            .into_iter()
            .filter_map(|entry| entry.ok())
            .filter(|entry| entry.file_type().is_file())
            .map(|entry| entry.path().to_path_buf())
            .collect()
    }

    // Helper function to collect directory names from a path
    // Helper function to get directory entries with WalkDir
    fn get_directory_entries(&self, dir_path: &Path) -> impl Iterator<Item = walkdir::DirEntry> {
        WalkDir::new(dir_path)
            .min_depth(1)
            .max_depth(1)
            .into_iter()
            .filter_map(|entry| entry.ok())
            .filter(|entry| entry.file_type().is_dir())
    }

    // Helper function to collect directory names from a path
    fn collect_dir_names(&self, dir_path: &Path) -> Result<Vec<String>, String> {
        if !dir_path.exists() {
            return Ok(Vec::new());
        }

        Ok(self
            .get_directory_entries(dir_path)
            .map(|entry| entry.file_name().to_string_lossy().to_string())
            .collect::<Vec<String>>())
    }

    // Load templates from the specified templates directory path.
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

    // Create a genanki Model from ModelData
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

    // Add notes to deck from CSV data
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

    // Collect all media files (model-specific and global)
    fn collect_all_media_files(&self, model_names: &[String]) -> Result<Vec<String>, String> {
        let mut all_media_files = Vec::new();

        // Collect model-specific media files using iterators
        all_media_files.extend(
            model_names
                .iter()
                .map(|model_name| self.load_model_data(model_name))
                .collect::<Result<Vec<_>, _>>()?
                .into_iter()
                .flat_map(|model_data| model_data.media_files.into_iter())
                .map(|media_path| media_path.to_string_lossy().to_string()),
        );

        // Collect global media files using iterators
        let global_media_path = self.project_path.join(MEDIA_DIR);
        all_media_files.extend(
            self.collect_files_from_dir(&global_media_path)
                .into_iter()
                .map(|file_path| file_path.to_string_lossy().to_string()),
        );

        Ok(all_media_files)
    }

    // Build complete deck with all models and notes
    fn build_complete_deck(&self) -> Result<(Deck, Vec<String>), String> {
        let deck_config = self.load_deck_config()?;
        let mut deck = Deck::new(
            deck_config.deck_id,
            &deck_config.name,
            &deck_config.description,
        );
        let model_names = self.get_available_models()?;

        model_names.iter().try_for_each(|model_name| {
            let model_data = self.load_model_data(model_name)?;
            let csv_data = self.load_csv_data(model_name)?;
            let model = self.create_genanki_model(model_name, &model_data);
            self.add_notes_to_deck(&mut deck, model, csv_data);
            Result::<(), String>::Ok(())
        })?;

        let all_media_files = self.collect_all_media_files(&model_names)?;
        Ok((deck, all_media_files))
    }

    // Write deck or package to file
    fn write_deck_to_file(
        &self,
        deck: Deck,
        media_files: Vec<String>,
        output_path: &str,
    ) -> Result<(), String> {
        if media_files.is_empty() {
            deck.write_to_file(output_path)
                .map_err(|e| format!("Failed to write deck: {:?}", e))?;
        } else {
            let media_refs: Vec<&str> = media_files.iter().map(|s| s.as_str()).collect();
            let mut package = Package::new(vec![deck], media_refs)
                .map_err(|e| format!("Failed to create package: {:?}", e))?;
            package
                .write_to_file(output_path)
                .map_err(|e| format!("Failed to write package: {:?}", e))?;
        }
        Ok(())
    }

    // Create directory structure with error handling
    fn create_dir_structure(&self, path: &Path) -> Result<(), String> {
        let dirs = [MODELS_DIR, DATA_DIR, MEDIA_DIR];
        for dir in &dirs {
            fs::create_dir_all(path.join(dir))
                .map_err(|e| format!("Failed to create {} directory: {}", dir, e))?;
        }
        Ok(())
    }

    // Write YAML file with error handling
    fn write_yaml<T: Serialize>(
        &self,
        path: PathBuf,
        data: &T,
        context: &str,
    ) -> Result<(), String> {
        let yaml_content = serde_yml::to_string(data)
            .map_err(|e| format!("Failed to serialize {}: {}", context, e))?;
        fs::write(path, yaml_content).map_err(|e| format!("Failed to write {}: {}", context, e))
    }

    // Public methods
    pub fn new(project_path: PathBuf) -> Result<Self, String> {
        if !project_path.exists() {
            return Err(format!(
                "Project path does not exist: {}",
                project_path.display()
            ));
        }
        Ok(Self { project_path })
    }

    pub fn load_deck_config(&self) -> Result<DeckConfig, String> {
        let deck_config_path = self.project_path.join(DECK_FILE);
        self.read_yaml(deck_config_path, DECK_FILE)
    }

    pub fn load_model_data(&self, model_name: &str) -> Result<ModelData, String> {
        let model_path = self.project_path.join(MODELS_DIR).join(model_name);

        // Load model config
        let fields_path = model_path.join(FIELDS_FILE);
        let config: ModelConfig = self.read_yaml(
            fields_path,
            &format!("{} for model {}", FIELDS_FILE, model_name),
        )?;

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

    pub fn get_available_models(&self) -> Result<Vec<String>, String> {
        let models_path = self.project_path.join(MODELS_DIR);
        self.collect_dir_names(&models_path)
    }

    pub fn load_csv_data(&self, model_name: &str) -> Result<Vec<Vec<String>>, String> {
        let csv_path = self
            .project_path
            .join(DATA_DIR)
            .join(format!("{}.csv", model_name));

        if !csv_path.exists() {
            return Ok(Vec::new());
        }

        let content = fs::read_to_string(&csv_path)
            .map_err(|e| format!("Failed to read CSV file for model {}: {}", model_name, e))?;

        let mut reader = csv::Reader::from_reader(content.as_bytes());
        let data: Result<Vec<Vec<String>>, String> = reader
            .records()
            .map(|result| {
                let record = result.map_err(|e| format!("Failed to parse CSV record: {}", e))?;
                Ok(record.iter().map(|s| s.to_string()).collect())
            })
            .collect();
        let data = data?;

        Ok(data)
    }
    pub fn add_csv_data(&self, model_name: &str, data: &PathBuf) -> Result<(), String> {
        let data_dir = self.project_path.join(DATA_DIR);
        fs::create_dir_all(&data_dir)
            .map_err(|e| format!("Failed to create data directory: {}", e))?;

        let target_path = data_dir.join(format!("{}.csv", model_name));

        fs::copy(data, &target_path)
            .map_err(|e| format!("Failed to copy CSV data for model {}: {}", model_name, e))?;

        Ok(())
    }

    pub fn build_deck(&self) -> Result<(), String> {
        let (_deck, _media_files) = self.build_complete_deck()?;
        Ok(())
    }

    pub fn export_deck(&self, output_path: PathBuf) -> Result<(), String> {
        let (deck, media_files) = self.build_complete_deck()?;
        self.write_deck_to_file(
            deck,
            media_files,
            output_path.to_str().ok_or("Invalid output path")?,
        )
    }

    pub fn create_project_template(
        project_path: PathBuf,
        deck_name: Option<String>,
        deck_description: Option<String>,
        author: Option<String>,
        model_name: Option<String>,
        fields: Option<Vec<String>>,
    ) -> Result<(), String> {
        let loader = Self {
            project_path: project_path.clone(),
        };

        // Create directory structure
        loader.create_dir_structure(&project_path)?;

        // Create sample deck.yaml
        let deck_config = DeckConfig {
            name: deck_name.unwrap_or_else(|| "Sample Deck".to_string()),
            description: deck_description.unwrap_or_else(|| "A sample Anki deck".to_string()),
            deck_id: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_else(|_| std::time::Duration::from_secs(0))
                .as_secs() as i64,
            author: author.or(Some("Generated by Fabricatio".to_string())),
        };
        loader.write_yaml(project_path.join(DECK_FILE), &deck_config, DECK_FILE)?;

        // Create sample model
        let model_name = model_name.unwrap_or_else(|| "basic_card".to_string());
        let model_path = project_path.join(MODELS_DIR).join(&model_name);
        fs::create_dir_all(&model_path)
            .map_err(|e| format!("Failed to create model directory: {}", e))?;

        let model_config = ModelConfig {
            model_id: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_else(|_| std::time::Duration::from_secs(0))
                .as_secs() as i64
                + 1,
            fields: fields.unwrap_or_else(|| vec!["Front".to_string(), "Back".to_string()]),
        };
        loader.write_yaml(model_path.join(FIELDS_FILE), &model_config, FIELDS_FILE)?;

        // Create sample template
        let template_path = model_path.join(TEMPLATE_DIR).join("card");
        fs::create_dir_all(&template_path)
            .map_err(|e| format!("Failed to create template directory: {}", e))?;

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

        for (filename, content) in &template_files {
            fs::write(template_path.join(filename), content)
                .map_err(|e| format!("Failed to write {}: {}", filename, e))?;
        }

        // Create sample CSV data
        fs::write(
            project_path
                .join(DATA_DIR)
                .join(format!("{}.csv", model_name)),
            "Front,Back\n\"What is the capital of France?\",\"Paris\"\n\"What is 2+2?\",\"4\"",
        )
        .map_err(|e| format!("Failed to write sample CSV: {}", e))?;

        Ok(())
    }
}
