use http::header::AUTHORIZATION;
use http::{HeaderMap, HeaderValue};
use secrecy::{ExposeSecret, SecretString};


pub(crate) fn build_headers(key: &SecretString) -> crate::Result<HeaderMap> {
    let mut h = HeaderMap::new();

    let mut auth_header =
        HeaderValue::from_str(format!("Bearer {}", key.expose_secret()).as_str())?;

    auth_header.set_sensitive(true);

    h.insert(AUTHORIZATION, auth_header);
    Ok(h)
}
