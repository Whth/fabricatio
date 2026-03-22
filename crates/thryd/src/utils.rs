use std::time::{SystemTime, UNIX_EPOCH};
use http::header::AUTHORIZATION;
use http::{HeaderMap, HeaderValue};
use secrecy::{ExposeSecret, SecretString};
pub type TimeStamp = u128;
pub(crate) fn current_timestamp() -> TimeStamp {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("Time went backwards")
        .as_millis()
}
pub(crate) fn build_headers(key: &SecretString) -> crate::Result<HeaderMap> {
    let mut h = HeaderMap::new();

    let mut auth_header =
        HeaderValue::from_str(format!("Bearer {}", key.expose_secret()).as_str())?;

    auth_header.set_sensitive(true);

    h.insert(AUTHORIZATION, auth_header);
    Ok(h)
}
