use polib::message::{Message as PoMessage, MessageMutView};
use polib::po_file::{parse, write};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::fs;
use std::io::BufWriter;
use std::path::PathBuf;

use error_mapping::*;

#[derive(Clone, Default)]
#[pyclass(get_all)]
struct Msg {
    id: String,
    txt: String,
}

#[pymethods]
impl Msg {
    #[new]
    fn new(id: String, txt: String) -> Self {
        Self { id, txt }
    }
}

impl From<Msg> for PoMessage {
    fn from(value: Msg) -> Self {
        let mut msg = PoMessage::default();
        msg.set_msgid(value.id);
        msg.set_msgstr(value.txt).expect("Failed to set msgstr");
        msg
    }
}

/// Reads a .po file and returns a vector of Message objects containing msgid and msgstr.
#[pyfunction]
fn read_pofile(file_path: PathBuf) -> PyResult<Vec<Msg>> {
    let catlog = parse(file_path.as_path()).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    Ok(catlog
        .messages()
        .map(|message| Msg {
            id: message.msgid().to_string(),
            txt: message.msgstr().unwrap_or_default().to_string(),
        })
        .collect())
}

/// Updates a .po file with the provided messages.
///
/// # Arguments
/// * file_path: Path to the .po file.
/// * messages: A vector of Message objects containing msgid and msgstr.
#[pyfunction]
fn update_pofile(file_path: PathBuf, messages: Vec<Msg>) -> PyResult<()> {
    let mut catalog =
        parse(file_path.as_path()).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    for msg in messages {
        catalog.append_or_update(PoMessage::from(msg))
    }
    let mut w = BufWriter::new(fs::File::open(file_path).into_pyresult()?);
    // Write the updated catalog back to file
    write(&catalog, &mut w).map_err(|e| PyRuntimeError::new_err(e.to_string()))?;

    Ok(())
}

/// Registers the functions in the module.
pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(read_pofile, m)?)?;
    m.add_function(wrap_pyfunction!(update_pofile, m)?)?;
    m.add_class::<Msg>()?;
    Ok(())
}
