#[derive(thiserror::Error, Debug)]
pub enum Error {
    #[error("IO error: {0}")]
    IO(#[from] std::io::Error),
    #[error("Deserialize error: {0}")]
    Deserialize(#[from] serde::de::value::Error),

    #[error("Serialize error: {0}")]
    Serialize(#[from] serde_yaml2::ser::Errors),

    #[error("Anki error: {0}")]
    Anki(#[from] genanki_rs_rev::Error),

    #[error("Path error: {0}")]
    Path(#[from] std::path::StripPrefixError),
}

pub type Result<T> = std::result::Result<T, Error>;
