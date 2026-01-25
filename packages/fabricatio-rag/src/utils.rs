#[inline]
pub(crate) fn wraped<T>(seq: Vec<T>) -> Vec<Option<T>> {
    seq.into_iter().map(Some).collect()
}
