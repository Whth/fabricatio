use std::sync::{Arc, Mutex};

/// A utility function that wraps any type T into an Arc<Mutex<T>>
///
/// This function is useful for sharing mutable data between multiple owners
/// in a thread-safe manner. It combines the atomic reference counting of Arc
/// with the mutual exclusion of Mutex to allow safe concurrent access.
///
/// # Examples
///
/// ```
/// use utils::*;
/// let shared_data = mwrap(42);
/// let mut guard = shared_data.lock().unwrap();
/// *guard += 1;
/// assert_eq!(*guard, 43);
/// ```
///
/// # Panics
///
/// This function itself does not panic, but accessing the wrapped value
/// through the Mutex may panic if the lock is poisoned.
#[inline]
pub fn mwrap<T>(item: T) -> Arc<Mutex<T>> {
    Arc::new(Mutex::new(item))
}
