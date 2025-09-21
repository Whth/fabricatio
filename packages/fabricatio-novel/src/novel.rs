use epub_builder::{EpubBuilder, EpubContent, Error as EpubError, ZipCommand};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::fs::{read, write};
use std::path::PathBuf;
use thiserror::Error;

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
    inner: Option<EpubBuilder<ZipCommand>>,
}

impl NovelBuilder {
    fn ensure_initialized_mut(&mut self) -> Result<&mut EpubBuilder<ZipCommand>, LocalError> {
        self.inner.as_mut().ok_or(LocalError::NotInitialized)
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
        let zip = ZipCommand::new().map_err(LocalError::Epub)?;
        let builder = EpubBuilder::new(zip).map_err(LocalError::Epub)?;
        slf.inner = Some(builder);
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
        let chapter_content = EpubContent::new(format!("{}.xhtml", title), content.as_bytes())
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

    /// Sets the CSS stylesheet for the novel.
    fn set_stylesheet(mut slf: PyRefMut<Self>, stylesheet: String) -> PyResult<PyRefMut<Self>> {
        slf.ensure_initialized_mut()?
            .stylesheet(stylesheet.as_bytes())
            .map_err(LocalError::Epub)?;
        Ok(slf)
    }

    /// Enables inline table of contents generation.
    fn add_inline_toc(mut slf: PyRefMut<Self>) -> PyResult<PyRefMut<Self>> {
        slf.ensure_initialized_mut()?.inline_toc();
        Ok(slf)
    }

    /// Exports the built novel to the specified file path.
    fn export(mut slf: PyRefMut<Self>, path: PathBuf) -> PyResult<PyRefMut<Self>> {
        let builder = slf.inner.take().ok_or(LocalError::NotInitialized)?;
        let mut bytes = vec![];
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
