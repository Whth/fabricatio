use epub_builder::EpubVersion::V30;
use epub_builder::{EpubBuilder, EpubContent, Error as EpubError, ZipLibrary};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::collections::hash_map::DefaultHasher;
use std::fs::{read, write};
use std::hash::{Hash, Hasher};
use std::path::PathBuf;
use thiserror::Error;

#[inline]
fn hash_to_filename(s: &str) -> String {
    let mut hasher = DefaultHasher::new();
    s.hash(&mut hasher);
    let hash = hasher.finish();
    format!("{:x}", hash)
}
#[derive(Error, Debug)]
enum LocalError {
    #[error(transparent)]
    Epub(#[from] EpubError),
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error("Novel not initialized")]
    NotInitialized,
}

impl From<LocalError> for PyErr {
    fn from(err: LocalError) -> PyErr {
        PyRuntimeError::new_err(err.to_string())
    }
}

/// A Python-exposed builder for creating EPUB novels.
#[pyclass]
#[derive(Default)]
struct NovelBuilder {
    inner: Option<EpubBuilder<ZipLibrary>>,
    css: String,
}

impl NovelBuilder {
    fn ensure_initialized_mut(&mut self) -> Result<&mut EpubBuilder<ZipLibrary>, LocalError> {
        self.inner.as_mut().ok_or(LocalError::NotInitialized)
    }

    fn add_css_inner(&mut self, css: String) -> Result<(), LocalError> {
        self.css.push('\n');
        self.css.push_str(&css);
        Ok(())
    }
}

#[pymethods]
impl NovelBuilder {
    /// Creates a new uninitialized NovelBuilder instance.
    #[new]
    fn new() -> PyResult<Self> {
        Ok(NovelBuilder::default())
    }

    /// Initializes a new EPUB novel builder.
    fn new_novel(mut slf: PyRefMut<Self>) -> PyResult<PyRefMut<Self>> {
        let zip = ZipLibrary::new().map_err(LocalError::Epub)?;
        let mut builder = EpubBuilder::new(zip).map_err(LocalError::Epub)?;
        builder.epub_version(V30);
        slf.inner = Some(builder);
        slf.css.clear();
        Ok(slf)
    }

    fn set_title(mut slf: PyRefMut<Self>, title: String) -> PyResult<PyRefMut<Self>> {
        slf.ensure_initialized_mut()?.set_title(title);
        Ok(slf)
    }

    /// Sets the novel description.
    fn set_description(mut slf: PyRefMut<Self>, description: String) -> PyResult<PyRefMut<Self>> {
        slf.ensure_initialized_mut()?
            .set_description(description.lines().map(String::from).collect::<Vec<_>>());

        Ok(slf)
    }
    /// Adds an author to the novel metadata.
    fn add_author(mut slf: PyRefMut<Self>, author: String) -> PyResult<PyRefMut<Self>> {
        slf.ensure_initialized_mut()?.add_author(author);
        Ok(slf)
    }

    /// Adds a chapter with given title and content.
    fn add_chapter(
        mut slf: PyRefMut<Self>,
        title: String,
        content: String,
    ) -> PyResult<PyRefMut<Self>> {
        let builder = slf.ensure_initialized_mut()?;
        let chapter_content = EpubContent::new(
            format!("{}.xhtml", hash_to_filename(&title)),
            content.as_bytes(),
        )
        .level(1)
        .title(&title);
        builder
            .add_content(chapter_content)
            .map_err(LocalError::Epub)?;
        Ok(slf)
    }

    /// Adds a cover image from the given file path.
    fn add_cover_image(
        mut slf: PyRefMut<Self>,
        path: PathBuf,
        source: PathBuf,
    ) -> PyResult<PyRefMut<Self>> {
        let builder = slf.ensure_initialized_mut()?;
        let data = read(&source).map_err(LocalError::Io)?;
        let mime = mime_guess::from_path(&source)
            .first_or_octet_stream()
            .to_string();
        builder
            .add_cover_image(path, &data[..], mime)
            .map_err(LocalError::Epub)?;
        Ok(slf)
    }

    /// Adds custom metadata key-value pair to the novel.
    fn add_metadata(
        mut slf: PyRefMut<Self>,
        key: String,
        value: String,
    ) -> PyResult<PyRefMut<Self>> {
        slf.ensure_initialized_mut()?
            .metadata(key, value)
            .map_err(LocalError::Epub)?;
        Ok(slf)
    }

    /// Adds CSS styles to the novel.
    fn add_css(mut slf: PyRefMut<Self>, css: String) -> PyResult<PyRefMut<Self>> {
        slf.add_css_inner(css)?;
        Ok(slf)
    }

    /// Adds a resource file to the novel.
    fn add_resource(
        mut slf: PyRefMut<Self>,
        path: PathBuf,
        source: PathBuf,
    ) -> PyResult<PyRefMut<Self>> {
        let builder = slf.ensure_initialized_mut()?;
        let data = read(&source).map_err(LocalError::Io)?;

        builder
            .add_resource(
                path,
                &data[..],
                mime_guess::from_path(&source)
                    .first_or_octet_stream()
                    .to_string(),
            )
            .map_err(LocalError::Epub)?;
        Ok(slf)
    }

    /// Adds a font file to the novel.
    fn add_font(
        mut slf: PyRefMut<Self>,
        font_family: String,
        source: PathBuf,
    ) -> PyResult<PyRefMut<Self>> {
        let data = read(&source).map_err(LocalError::Io)?;
        slf.ensure_initialized_mut()?
            .add_resource(
                format!("fonts/{}.ttf", font_family),
                &data[..],
                mime_guess::from_path(&source)
                    .first_or_octet_stream()
                    .to_string(),
            )
            .map_err(LocalError::Epub)?;

        slf.add_css_inner(format!(
            "@font-face {{
                    font-family: '{}';
                    src: url('fonts/{}.ttf');
                }}",
            font_family, font_family
        ))?;

        Ok(slf)
    }

    /// Enables inline table of contents generation.
    fn add_inline_toc(mut slf: PyRefMut<Self>) -> PyResult<PyRefMut<Self>> {
        slf.ensure_initialized_mut()?.inline_toc();
        Ok(slf)
    }

    /// Exports the built novel to the specified file path.
    fn export(mut slf: PyRefMut<Self>, path: PathBuf) -> PyResult<PyRefMut<Self>> {
        let mut builder = slf.inner.take().ok_or(LocalError::NotInitialized)?;
        let mut bytes = vec![];

        builder
            .stylesheet(slf.css.drain(..).as_str().as_bytes())
            .map_err(LocalError::Epub)?;
        builder.generate(&mut bytes).map_err(LocalError::Epub)?;

        write(path.as_path(), bytes).map_err(LocalError::Io)?;
        Ok(slf)
    }
}

/// Registers the NovelBuilder class with the Python module.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<NovelBuilder>()?;
    Ok(())
}
