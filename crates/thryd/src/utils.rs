use std::sync::Arc;
use tokio::sync::Mutex;

#[inline]
pub(crate) fn am<T>(s: T) -> Arc<Mutex<T>> {
    Arc::new(Mutex::new(s))
}