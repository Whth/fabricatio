use http::header::AUTHORIZATION;
use http::{HeaderMap, HeaderValue};
use secrecy::{ExposeSecret, SecretString};
use std::sync::Arc;
use tokio::sync::Mutex;

#[inline]
pub(crate) fn am<T>(s: T) -> Arc<Mutex<T>> {
    Arc::new(Mutex::new(s))
}

pub(crate) fn build_headers(key: &SecretString) -> crate::Result<HeaderMap> {
    let mut h = HeaderMap::new();

    let mut auth_header =
        HeaderValue::from_str(format!("Bearer {}", key.expose_secret()).as_str())?;

    auth_header.set_sensitive(true);

    h.insert(AUTHORIZATION, auth_header);
    Ok(h)
}
