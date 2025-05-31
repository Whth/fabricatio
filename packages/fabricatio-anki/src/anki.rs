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
        Ok(Self {
            project_path: path,
        })
    }

    fn load_deck_config(&self) -> PyResult<DeckConfig> {
        let deck_config_path = self.project_path.join("deck.yaml");
        let content = fs::read_to_string(&deck_config_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
                format!("Failed to read deck.yaml: {}", e)
            ))?;

        serde_yml::from_str(&content)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Failed to parse deck.yaml: {}", e)
            ))
    }

    fn load_model_data(&self, model_name: &str) -> PyResult<ModelData> {
        let model_path = self.project_path.join("models").join(model_name);

        // Load model config
        let fields_path = model_path.join("fields.yaml");
        let fields_content = fs::read_to_string(&fields_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
                format!("Failed to read fields.yaml for model {}: {}", model_name, e)
            ))?;

        let config: ModelConfig = serde_yml::from_str(&fields_content)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Failed to parse fields.yaml for model {}: {}", model_name, e)
            ))?;

        // Load templates
        let templates_path = model_path.join("templates");
        let mut templates = Vec::new();

        if templates_path.exists() {
            for entry in fs::read_dir(&templates_path)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
                    format!("Failed to read templates directory for model {}: {}", model_name, e)
                ))? {
                let entry = entry.map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
                    format!("Failed to read template entry: {}", e)
                ))?;

                if entry.file_type().map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
                    format!("Failed to get file type: {}", e)
                ))?.is_dir() {
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

        // Load media files
        let mut media_files = Vec::new();
        let model_media_path = model_path.join("media");
        if model_media_path.exists() {
            if let Ok(entries) = fs::read_dir(&model_media_path) {
                for entry in entries {
                    if let Ok(entry) = entry {
                        if let Ok(file_type) = entry.file_type() {
                            if file_type.is_file() {
                                media_files.push(entry.path());
                            }
                        }
                    }
                }
            }
        }

        Ok(ModelData {
            config,
            templates,
            media_files,
        })
    }

    fn get_available_models(&self) -> PyResult<Vec<String>> {
        let models_path = self.project_path.join("models");
        let mut models = Vec::new();

        if models_path.exists() {
            for entry in fs::read_dir(&models_path)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
                    format!("Failed to read models directory: {}", e)
                ))? {
                let entry = entry.map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
                    format!("Failed to read model entry: {}", e)
                ))?;

                if entry.file_type().map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
                    format!("Failed to get file type: {}", e)
                ))?.is_dir() {
                    models.push(entry.file_name().to_string_lossy().to_string());
                }
            }
        }

        Ok(models)
    }

    fn load_csv_data(&self, model_name: &str) -> PyResult<Vec<Vec<String>>> {
        let csv_path = self.project_path.join("data").join(format!("{}.csv", model_name));

        if !csv_path.exists() {
            return Ok(Vec::new());
        }

        let content = fs::read_to_string(&csv_path)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
                format!("Failed to read CSV file for model {}: {}", model_name, e)
            ))?;

        let mut reader = csv::Reader::from_reader(content.as_bytes());
        let mut data = Vec::new();

        for result in reader.records() {
            let record = result.map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                format!("Failed to parse CSV record: {}", e)
            ))?;
            data.push(record.iter().map(|s| s.to_string()).collect());
        }

        Ok(data)
    }

    fn build_deck(&self) -> PyResult<()> {
        let deck_config = self.load_deck_config()?;
        let mut deck = Deck::new(deck_config.deck_id, &deck_config.name, &deck_config.description);

        let model_names = self.get_available_models()?;
        let mut all_media_files = Vec::new();

        for model_name in model_names {
            let model_data = self.load_model_data(&model_name)?;
            let csv_data = self.load_csv_data(&model_name)?;

            // Create genanki Model
            let model_fields: Vec<Field> = model_data.config.fields.iter()
                .map(|f| Field::new(f))
                .collect();

            let model_templates: Vec<Template> = model_data.templates.iter()
                .map(|t| Template::new(&t.name)
                    .qfmt(&t.front_html)
                    .afmt(&t.back_html))
                .collect();

            // Combine all CSS from templates
            let combined_css = model_data.templates.iter()
                .map(|t| t.style_css.as_str())
                .collect::<Vec<_>>()
                .join("\n");

            let model = if combined_css.is_empty() {
                Model::new(model_data.config.model_id, &model_name, model_fields, model_templates)
            } else {
                Model::new(model_data.config.model_id, &model_name, model_fields, model_templates)
                    .css(combined_css)
            };

            // Add notes from CSV data
            for row in csv_data {
                if !row.is_empty() {
                    let field_refs: Vec<&str> = row.iter().map(|s| s.as_str()).collect();
                    if let Ok(note) = Note::new(model.clone(), field_refs) {
                        deck.add_note(note);
                    }
                }
            }

            // Collect media files
            for media_path in &model_data.media_files {
                all_media_files.push(media_path.to_string_lossy().to_string());
            }
        }

        // Add global media files
        let global_media_path = self.project_path.join("media");
        if global_media_path.exists() {
            if let Ok(entries) = fs::read_dir(&global_media_path) {
                for entry in entries {
                    if let Ok(entry) = entry {
                        if let Ok(file_type) = entry.file_type() {
                            if file_type.is_file() {
                                all_media_files.push(entry.path().to_string_lossy().to_string());
                            }
                        }
                    }
                }
            }
        }

        Ok(())
    }

    fn export_deck(&self, output_path: String) -> PyResult<()> {
        let deck_config = self.load_deck_config()?;
        let mut deck = Deck::new(deck_config.deck_id, &deck_config.name, &deck_config.description);

        let model_names = self.get_available_models()?;
        let mut all_media_files = Vec::new();

        for model_name in model_names {
            let model_data = self.load_model_data(&model_name)?;
            let csv_data = self.load_csv_data(&model_name)?;

            // Create genanki Model
            let model_fields: Vec<Field> = model_data.config.fields.iter()
                .map(|f| Field::new(f))
                .collect();

            let model_templates: Vec<Template> = model_data.templates.iter()
                .map(|t| Template::new(&t.name)
                    .qfmt(&t.front_html)
                    .afmt(&t.back_html))
                .collect();

            // Combine all CSS from templates
            let combined_css = model_data.templates.iter()
                .map(|t| t.style_css.as_str())
                .collect::<Vec<_>>()
                .join("\n");

            let model = if combined_css.is_empty() {
                Model::new(model_data.config.model_id, &model_name, model_fields, model_templates)
            } else {
                Model::new(model_data.config.model_id, &model_name, model_fields, model_templates)
                    .css(combined_css)
            };

            // Add notes from CSV data
            for row in csv_data {
                if !row.is_empty() {
                    let field_refs: Vec<&str> = row.iter().map(|s| s.as_str()).collect();
                    if let Ok(note) = Note::new(model.clone(), field_refs) {
                        deck.add_note(note);
                    }
                }
            }

            // Collect media files
            for media_path in &model_data.media_files {
                all_media_files.push(media_path.to_string_lossy().to_string());
            }
        }

        // Add global media files
        let global_media_path = self.project_path.join("media");
        if global_media_path.exists() {
            if let Ok(entries) = fs::read_dir(&global_media_path) {
                for entry in entries {
                    if let Ok(entry) = entry {
                        if let Ok(file_type) = entry.file_type() {
                            if file_type.is_file() {
                                all_media_files.push(entry.path().to_string_lossy().to_string());
                            }
                        }
                    }
                }
            }
        }

        // Export as package if there are media files, otherwise as deck
        if all_media_files.is_empty() {
            deck.write_to_file(&output_path)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
                    format!("Failed to write deck: {:?}", e)
                ))?;
        } else {
            let media_refs: Vec<&str> = all_media_files.iter().map(|s| s.as_str()).collect();
            let mut package = Package::new(vec![deck], media_refs)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    format!("Failed to create package: {:?}", e)
                ))?;
            package.write_to_file(&output_path)
                .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(
                    format!("Failed to write package: {:?}", e)
                ))?;
        }

        Ok(())
    }

    fn create_project_template(&self, project_path: String) -> PyResult<()> {
        let path = Path::new(&project_path);

        // Create directory structure
        fs::create_dir_all(path.join("models")).map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to create models directory: {}", e)))?;
        fs::create_dir_all(path.join("data")).map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to create data directory: {}", e)))?;
        fs::create_dir_all(path.join("media")).map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to create media directory: {}", e)))?;

        // Create sample deck.yaml
        let deck_config = DeckConfig {
            name: "Sample Deck".to_string(),
            description: "A sample Anki deck".to_string(),
            deck_id: 1234567890,
            author: Some("Generated by Fabricatio".to_string()),
        };

        let deck_yaml = serde_yml::to_string(&deck_config)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to serialize deck config: {}", e)))?;

        fs::write(path.join("deck.yaml"), deck_yaml)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to write deck.yaml: {}", e)))?;

        // Create sample model
        let model_path = path.join("models").join("basic_card");
        fs::create_dir_all(&model_path).map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to create model directory: {}", e)))?;

        let model_config = ModelConfig {
            model_id: 1607392319,
            fields: vec!["Front".to_string(), "Back".to_string()],
        };

        let fields_yaml = serde_yml::to_string(&model_config)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to serialize model config: {}", e)))?;

        fs::write(model_path.join("fields.yaml"), fields_yaml)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to write fields.yaml: {}", e)))?;

        // Create sample template
        let template_path = model_path.join("templates").join("card");
        fs::create_dir_all(&template_path).map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to create template directory: {}", e)))?;

        fs::write(template_path.join("front.html"), "{{Front}}")
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to write front.html: {}", e)))?;

        fs::write(template_path.join("back.html"), "{{FrontSide}}\n\n<hr id=\"answer\">\n\n{{Back}}")
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to write back.html: {}", e)))?;

        fs::write(template_path.join("style.css"), ".card {\n  font-family: arial;\n  font-size: 20px;\n  text-align: center;\n  color: black;\n  background-color: white;\n}")
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to write style.css: {}", e)))?;

        // Create sample CSV data
        fs::write(path.join("data").join("basic_card.csv"), "Front,Back\n\"What is the capital of France?\",\"Paris\"\n\"What is 2+2?\",\"4\"")
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("Failed to write sample CSV: {}", e)))?;

        Ok(())
    }
}

pub(crate) fn register(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<AnkiDeckLoader>()?;
    Ok(())
}