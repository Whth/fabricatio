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
use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};


#[derive(Debug, Serialize, Deserialize)]
#[pyclass]
struct DeckConfig {
    name: String,
    description: String,
    deck_id: i64,
    author: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
#[pyclass]
struct ModelConfig {
    model_id: i64,
    fields: Vec<String>,
}

#[derive(Debug, Clone)]
struct TemplateConfig {
    name: String,
    front_html: String,
    back_html: String,
    style_css: String,
}

#[derive(Debug)]
#[pyclass]
struct ModelData {
    config: ModelConfig,
    templates: Vec<TemplateConfig>,
    media_files: Vec<PathBuf>,
}

#[pyclass]
struct AnkiDeckLoader {
    project_path: PathBuf,
}

impl AnkiDeckLoader {
    /// Helper function to map IO errors to PyIOError
    fn io_error(message: &str, error: std::io::Error) -> PyErr {
        PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("{}: {}", message, error))
    }

    /// Helper function to map serialization errors to PyValueError
    fn value_error(message: &str, error: impl std::fmt::Display) -> PyErr {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("{}: {}", message, error))
    }

    /// Helper function to read YAML file and deserialize
    fn read_yaml<T: for<'de> Deserialize<'de>>(&self, file_path: PathBuf, context: &str) -> PyResult<T> {
        let content = fs::read_to_string(&file_path)
            .map_err(|e| Self::io_error(&format!("Failed to read {}", context), e))?;

        serde_yml::from_str(&content)
            .map_err(|e| Self::value_error(&format!("Failed to parse {}", context), e))
    }

    /// Helper function to collect files from a directory
    fn collect_files_from_dir(&self, dir_path: &Path) -> Vec<PathBuf> {
        let mut files = Vec::new();
        if let Ok(entries) = fs::read_dir(dir_path) {
            for entry in entries.flatten() {
                if let Ok(file_type) = entry.file_type() {
                    if file_type.is_file() {
                        files.push(entry.path());
                    }
                }
            }
        }
        files
    }

    /// Helper function to collect directory names from a path
    fn collect_dir_names(&self, dir_path: &Path) -> PyResult<Vec<String>> {
        let mut dirs = Vec::new();
        if dir_path.exists() {
            for entry in fs::read_dir(dir_path)
                .map_err(|e| Self::io_error("Failed to read directory", e))? {
                let entry = entry.map_err(|e| Self::io_error("Failed to read directory entry", e))?;
                if entry.file_type()
                    .map_err(|e| Self::io_error("Failed to get file type", e))?
                    .is_dir() {
                    dirs.push(entry.file_name().to_string_lossy().to_string());
                }
            }
        }
        Ok(dirs)
    }

    /// Load templates from the templates directory
    fn load_templates(&self, templates_path: &Path) -> Vec<TemplateConfig> {
        let mut templates = Vec::new();
        if !templates_path.exists() {
            return templates;
        }

        if let Ok(entries) = fs::read_dir(templates_path) {
            for entry in entries.flatten() {
                if let Ok(file_type) = entry.file_type() {
                    if file_type.is_dir() {
                        let template_name = entry.file_name().to_string_lossy().to_string();
                        let template_path = entry.path();

                        let front_html = fs::read_to_string(template_path.join("front.html"))
                            .unwrap_or_default();
                        let back_html = fs::read_to_string(template_path.join("back.html"))
                            .unwrap_or_default();
                        let style_css = fs::read_to_string(template_path.join("style.css"))
                            .unwrap_or_default();

                        templates.push(TemplateConfig {
                            name: template_name,
                            front_html,
                            back_html,
                            style_css,
                        });
                    }
                }
            }
        }
        templates
    }

    /// Create a genanki Model from ModelData
    fn create_genanki_model(&self, model_name: &str, model_data: &ModelData) -> Model {
        let model_fields: Vec<Field> = model_data.config.fields.iter()
            .map(|f| Field::new(f))
            .collect();

        let model_templates: Vec<Template> = model_data.templates.iter()
            .map(|t| Template::new(&t.name)
                .qfmt(&t.front_html)
                .afmt(&t.back_html))
            .collect();

        let combined_css = model_data.templates.iter()
            .map(|t| t.style_css.as_str())
            .collect::<Vec<_>>()
            .join("\n");

        let mut model = Model::new(model_data.config.model_id, model_name, model_fields, model_templates);
        if !combined_css.is_empty() {
            model = model.css(combined_css);
        }
        model
    }

    /// Add notes to deck from CSV data
    fn add_notes_to_deck(&self, deck: &mut Deck, model: Model, csv_data: Vec<Vec<String>>) {
        for row in csv_data {
            if !row.is_empty() {
                let field_refs: Vec<&str> = row.iter().map(|s| s.as_str()).collect();
                if let Ok(note) = Note::new(model.clone(), field_refs) {
                    deck.add_note(note);
                }
            }
        }
    }

    /// Collect all media files (model-specific and global)
    fn collect_all_media_files(&self, model_names: &[String]) -> PyResult<Vec<String>> {
        let mut all_media_files = Vec::new();

        // Collect model-specific media files
        for model_name in model_names {
            let model_data = self.load_model_data(model_name)?;
            for media_path in &model_data.media_files {
                all_media_files.push(media_path.to_string_lossy().to_string());
            }
        }

        // Collect global media files
        let global_media_path = self.project_path.join("media");
        for file_path in self.collect_files_from_dir(&global_media_path) {
            all_media_files.push(file_path.to_string_lossy().to_string());
        }

        Ok(all_media_files)
    }

    /// Build complete deck with all models and notes
    fn build_complete_deck(&self) -> PyResult<(Deck, Vec<String>)> {
        let deck_config = self.load_deck_config()?;
        let mut deck = Deck::new(deck_config.deck_id, &deck_config.name, &deck_config.description);
        let model_names = self.get_available_models()?;

        for model_name in &model_names {
            let model_data = self.load_model_data(model_name)?;
            let csv_data = self.load_csv_data(model_name)?;
            let model = self.create_genanki_model(model_name, &model_data);
            self.add_notes_to_deck(&mut deck, model, csv_data);
        }

        let all_media_files = self.collect_all_media_files(&model_names)?;
        Ok((deck, all_media_files))
    }

    /// Write deck or package to file
    fn write_deck_to_file(&self, deck: Deck, media_files: Vec<String>, output_path: &str) -> PyResult<()> {
        if media_files.is_empty() {
            deck.write_to_file(output_path)
                .map_err(|e| Self::io_error("Failed to write deck",
                                            std::io::Error::new(std::io::ErrorKind::Other, format!("{:?}", e))))?;
        } else {
            let media_refs: Vec<&str> = media_files.iter().map(|s| s.as_str()).collect();
            let mut package = Package::new(vec![deck], media_refs)
                .map_err(|e| Self::value_error("Failed to create package", format!("{:?}", e)))?;
            package.write_to_file(output_path)
                .map_err(|e| Self::io_error("Failed to write package",
                                            std::io::Error::new(std::io::ErrorKind::Other, format!("{:?}", e))))?;
        }
        Ok(())
    }

    /// Create directory structure with error handling
    fn create_dir_structure(&self, path: &Path) -> PyResult<()> {
        let dirs = ["models", "data", "media"];
        for dir in &dirs {
            fs::create_dir_all(path.join(dir))
                .map_err(|e| Self::io_error(&format!("Failed to create {} directory", dir), e))?;
        }
        Ok(())
    }

    /// Write YAML file with error handling
    fn write_yaml<T: Serialize>(&self, path: PathBuf, data: &T, context: &str) -> PyResult<()> {
        let yaml_content = serde_yml::to_string(data)
            .map_err(|e| Self::value_error(&format!("Failed to serialize {}", context), e))?;
        fs::write(path, yaml_content)
            .map_err(|e| Self::io_error(&format!("Failed to write {}", context), e))
    }
}

#[pymethods]
impl AnkiDeckLoader {
    #[new]
    fn new(project_path: String) -> PyResult<Self> {
        let path = PathBuf::from(project_path);
        if !path.exists() {
            return Err(PyErr::new::<pyo3::exceptions::PyFileNotFoundError, _>(
                format!("Project path does not exist: {}", path.display())
            ));
        }
        Ok(Self { project_path: path })
    }

    fn load_deck_config(&self) -> PyResult<DeckConfig> {
        let deck_config_path = self.project_path.join("deck.yaml");
        self.read_yaml(deck_config_path, "deck.yaml")
    }

    fn load_model_data(&self, model_name: &str) -> PyResult<ModelData> {
        let model_path = self.project_path.join("models").join(model_name);

        // Load model config
        let fields_path = model_path.join("fields.yaml");
        let config: ModelConfig = self.read_yaml(fields_path, &format!("fields.yaml for model {}", model_name))?;

        // Load templates
        let templates_path = model_path.join("templates");
        let templates = self.load_templates(&templates_path);

        // Load media files
        let media_files = self.collect_files_from_dir(&model_path.join("media"));

        Ok(ModelData {
            config,
            templates,
            media_files,
        })
    }

    fn get_available_models(&self) -> PyResult<Vec<String>> {
        let models_path = self.project_path.join("models");
        self.collect_dir_names(&models_path)
    }

    fn load_csv_data(&self, model_name: &str) -> PyResult<Vec<Vec<String>>> {
        let csv_path = self.project_path.join("data").join(format!("{}.csv", model_name));

        if !csv_path.exists() {
            return Ok(Vec::new());
        }

        let content = fs::read_to_string(&csv_path)
            .map_err(|e| Self::io_error(&format!("Failed to read CSV file for model {}", model_name), e))?;

        let mut reader = csv::Reader::from_reader(content.as_bytes());
        let mut data = Vec::new();

        for result in reader.records() {
            let record = result.map_err(|e| Self::value_error("Failed to parse CSV record", e))?;
            data.push(record.iter().map(|s| s.to_string()).collect());
        }

        Ok(data)
    }

    fn build_deck(&self) -> PyResult<()> {
        let (_deck, _media_files) = self.build_complete_deck()?;
        Ok(())
    }

    fn export_deck(&self, output_path: String) -> PyResult<()> {
        let (deck, media_files) = self.build_complete_deck()?;
        self.write_deck_to_file(deck, media_files, &output_path)
    }


    #[staticmethod]
    #[pyo3(signature = ( project_path, deck_name = None, deck_description = None, author = None, model_name = None, fields = None)
    )]
    fn create_project_template(
        project_path: String,
        deck_name: Option<String>,
        deck_description: Option<String>,
        author: Option<String>,
        model_name: Option<String>,
        fields: Option<Vec<String>>,
    ) -> PyResult<()> {
        let path = PathBuf::from(&project_path);
        let loader = Self { project_path: path.clone() };

        // Create directory structure
        loader.create_dir_structure(&path)?;

        // Create sample deck.yaml
        let deck_config = DeckConfig {
            name: deck_name.unwrap_or_else(|| "Sample Deck".to_string()),
            description: deck_description.unwrap_or_else(|| "A sample Anki deck".to_string()),
            deck_id: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_else(|_| std::time::Duration::from_secs(0))
                .as_secs() as i64,
            author: author.or_else(|| Some("Generated by Fabricatio".to_string())),
        };
        loader.write_yaml(path.join("deck.yaml"), &deck_config, "deck.yaml")?;

        // Create sample model
        let model_name = model_name.unwrap_or_else(|| "basic_card".to_string());
        let model_path = path.join("models").join(&model_name);
        fs::create_dir_all(&model_path)
            .map_err(|e| Self::io_error("Failed to create model directory", e))?;

        let model_config = ModelConfig {
            model_id: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_else(|_| std::time::Duration::from_secs(0))
                .as_secs() as i64 + 1,
            fields: fields.unwrap_or_else(|| vec!["Front".to_string(), "Back".to_string()]),
        };
        loader.write_yaml(model_path.join("fields.yaml"), &model_config, "fields.yaml")?;

        // Create sample template
        let template_path = model_path.join("templates").join("card");
        fs::create_dir_all(&template_path)
            .map_err(|e| Self::io_error("Failed to create template directory", e))?;

        let template_files = [
            ("front.html", "{{Front}}"),
            ("back.html", "{{FrontSide}}\n\n<hr id=\"answer\">\n\n{{Back}}"),
            ("style.css", ".card {\n  font-family: arial;\n  font-size: 20px;\n  text-align: center;\n  color: black;\n  background-color: white;\n}"),
        ];

        for (filename, content) in &template_files {
            fs::write(template_path.join(filename), content)
                .map_err(|e| Self::io_error(&format!("Failed to write {}", filename), e))?;
        }

        // Create sample CSV data
        fs::write(
            path.join("data").join(format!("{}.csv", model_name)),
            "Front,Back\n\"What is the capital of France?\",\"Paris\"\n\"What is 2+2?\",\"4\"",
        ).map_err(|e| Self::io_error("Failed to write sample CSV", e))?;

        Ok(())
    }
}

pub(crate) fn register(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<AnkiDeckLoader>()?;
    Ok(())
}