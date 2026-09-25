//! Character n-gram frequencies: the counting machinery the vocabulary measure is built on.
//!
//! Windows are cut from the text **without its whitespace**, the form every measure of this crate
//! compacts to as well, so a Chinese and an English text are measured by one rule and no window
//! spans a line break. A window is packed into one integer — 21 bits per scalar value, the width of
//! Unicode — so counting needs neither a string per window nor a hash of one.

use std::mem::size_of;

/// Bits one scalar value occupies in a packed window: Unicode's largest code point is U+10FFFF.
const CHAR_BITS: u32 = 21;

/// The longest window a `u128` key can pack: 6 x 21 = 126 bits.
///
/// Every size up to this one is measurable, which is the range the vocabulary measure names.
pub(crate) const MAX_N: usize = 6;

/// A window packed into an integer, narrow enough to keep the sort buffer small where it fits.
trait Window: Copy + Ord {
    /// The window whose scalar values are packed into `packed`, first value most significant.
    fn from_packed(packed: u128) -> Self;

    /// The packed form, all the counter compares and sorts.
    fn packed(self) -> u128;
}

impl Window for u64 {
    fn from_packed(packed: u128) -> Self {
        packed as u64
    }

    fn packed(self) -> u128 {
        self as u128
    }
}

impl Window for u128 {
    fn from_packed(packed: u128) -> Self {
        packed
    }

    fn packed(self) -> u128 {
        self
    }
}

/// The frequency table of one window size over one text.
pub(crate) struct NGramTally {
    /// How many characters one window spans.
    pub(crate) size: usize,

    /// How many windows the text holds, `0` when the text is shorter than one window.
    pub(crate) total_slots: usize,

    /// How many of those windows are distinct.
    pub(crate) distinct_grams: usize,

    /// How many distinct windows occur more than once.
    pub(crate) repeated_grams: usize,

    /// How many window slots hold a window that occurs more than once.
    pub(crate) recycled_slots: usize,

    /// The grams the caller named, most frequent first, ties in code point order.
    pub(crate) grams: Vec<(String, u32)>,
}

impl NGramTally {
    /// An empty table for a text too short to hold one window.
    fn empty(size: usize) -> Self {
        Self {
            size,
            total_slots: 0,
            distinct_grams: 0,
            repeated_grams: 0,
            recycled_slots: 0,
            grams: Vec::new(),
        }
    }

    /// Count one size, naming at most `named` of its grams.
    ///
    /// `0` names no gram at all and returns the counts alone: how many windows the text holds, how
    /// many of them are distinct and how many repeat does not depend on how many are named.
    pub(crate) fn of(chars: &[char], size: usize, named: usize) -> Self {
        match size {
            1..=3 => Self::counted::<u64>(chars, size, named),
            _ => Self::counted::<u128>(chars, size, named),
        }
    }

    /// Count one size with the narrowest key that holds it, sorted and run-length aggregated.
    ///
    /// Three scalar values fit `u64`, six need `u128`. Sorting a vector of packed keys keeps the
    /// count exact and the memory predictable: the peak is one key per window, and a hash map of the
    /// same windows would cost several times that. Only the named grams are ranked and unpacked —
    /// the rest of the table stays packed.
    fn counted<K: Window>(chars: &[char], size: usize, named: usize) -> Self {
        debug_assert!(
            CHAR_BITS as usize * size <= size_of::<K>() * 8,
            "a {size}-window does not fit a {}-bit key",
            size_of::<K>() * 8
        );
        if chars.len() < size {
            return Self::empty(size);
        }

        let mut keys: Vec<K> = Vec::new();
        pack(chars, size, &mut keys);
        keys.sort_unstable();

        let mut tally = Self {
            size,
            total_slots: keys.len(),
            distinct_grams: 0,
            repeated_grams: 0,
            recycled_slots: 0,
            grams: Vec::new(),
        };
        let mut ranked: Vec<(K, u32)> = Vec::new();
        runs(&keys, |key, count| {
            tally.distinct_grams += 1;
            if count > 1 {
                tally.repeated_grams += 1;
                tally.recycled_slots += count as usize;
            }
            ranked.push((key, count));
        });
        let order = |left: &(K, u32), right: &(K, u32)| {
            right.1.cmp(&left.1).then_with(|| left.0.cmp(&right.0))
        };
        if named < ranked.len() {
            // Only the named grams are ever read, so the tail is selected away rather than sorted and
            // unpacked: naming a few grams of every size costs those few and no more.
            ranked.select_nth_unstable_by(named, order);
            ranked.truncate(named);
        }
        ranked.sort_unstable_by(order);
        tally.grams = ranked
            .into_iter()
            .map(|(key, count)| (Self::unpack(key, size), count))
            .collect();
        tally
    }

    /// The text of a packed window.
    fn unpack<K: Window>(key: K, size: usize) -> String {
        let packed = key.packed();
        (0..size)
            .map(|position| {
                let shift = CHAR_BITS * (size - 1 - position) as u32;
                char::from_u32(((packed >> shift) & 0x1f_ffff) as u32)
                    .unwrap_or(char::REPLACEMENT_CHARACTER)
            })
            .collect()
    }
}

/// How much of a text's n-gram vocabulary repeats inside its own measurement window.
///
/// The text is cut into windows of consecutive n-grams and every window is measured on its own, so
/// the rate does not follow the text's length: over the whole text a long one would always look more
/// repetitive than a short one, because it gave its n-grams more chances to meet again. A trailing
/// block shorter than `window` is dropped, and a text shorter than one window is measured as the
/// single window it fits in.
pub(crate) struct NGramRecycling {
    /// How many windows the rate was measured over, `0` when the text holds no n-gram.
    pub(crate) windows: usize,

    /// The mean number of slots per 1000 that hold an n-gram their own window repeats.
    pub(crate) recycled_per_1k: f64,
}

impl NGramRecycling {
    /// Measure one size over the whole text: the rate of its windows and the slots behind them.
    pub(crate) fn of(chars: &[char], size: usize, window: usize) -> Self {
        match size {
            1..=3 => Self::with_key::<u64>(chars, size, window),
            _ => Self::with_key::<u128>(chars, size, window),
        }
    }

    /// Measure with the narrowest key that holds the size, the packing the frequency tables use.
    fn with_key<K: Window>(chars: &[char], size: usize, window: usize) -> Self {
        let total_slots = chars.len().saturating_sub(size - 1);
        let mut keys: Vec<K> = Vec::new();
        let mut windows: usize = 0;
        let mut total = 0.0;
        let mut start = 0;
        while start + window <= total_slots {
            let span = &chars[start..start + window + size - 1];
            total += Self::window_recycled(span, size, &mut keys) as f64 / window as f64 * 1000.0;
            windows += 1;
            start += window;
        }
        if windows == 0 && total_slots > 0 {
            // A text shorter than one window is measured as the single window it fits in.
            total =
                Self::window_recycled(chars, size, &mut keys) as f64 / total_slots as f64 * 1000.0;
            windows = 1;
        }
        Self {
            windows,
            recycled_per_1k: if windows == 0 {
                0.0
            } else {
                total / windows as f64
            },
        }
    }

    /// How many slots of one window hold an n-gram that window repeats.
    fn window_recycled<K: Window>(chars: &[char], size: usize, keys: &mut Vec<K>) -> usize {
        pack(chars, size, keys);
        keys.sort_unstable();
        let mut recycled = 0;
        runs(keys, |_, count| {
            if count > 1 {
                recycled += count as usize;
            }
        });
        recycled
    }
}

/// Pack every window of `chars` into `keys`, in text order, reusing the vector.
///
/// Every caller cuts its windows from a text at least `size` long, so a shorter one never reaches here.
fn pack<K: Window>(chars: &[char], size: usize, keys: &mut Vec<K>) {
    keys.clear();
    keys.reserve(chars.len().saturating_sub(size - 1));
    let mask = (1u128 << (CHAR_BITS * size as u32)) - 1;
    let mut packed: u128 = 0;
    for (position, scalar) in chars.iter().enumerate() {
        packed = ((packed << CHAR_BITS) | *scalar as u128) & mask;
        if position + 1 >= size {
            keys.push(K::from_packed(packed));
        }
    }
}

/// Walk the equal runs of a sorted key slice, handing every run its key and how often it occurs.
///
/// Shared by the two readers of packed windows: the frequency table and the recycling rate.
fn runs<K: Window>(keys: &[K], mut on_run: impl FnMut(K, u32)) {
    let mut index = 0;
    while index < keys.len() {
        let key = keys[index];
        let mut end = index + 1;
        while end < keys.len() && keys[end] == key {
            end += 1;
        }
        on_run(key, (end - index) as u32);
        index = end;
    }
}

/// The window size a measure may carry: `1..=MAX_N`, the range one packed key holds.
pub(crate) fn check_size(size: usize) -> Result<(), String> {
    if !(1..=MAX_N).contains(&size) {
        return Err(format!("size must be in 1..={MAX_N}, got {size}"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::text::{IDEOGRAPHS, compact};
    use std::collections::HashMap;

    /// The counts of every window of `size`, the plain form the tally has to reproduce.
    fn brute(text: &str, size: usize) -> HashMap<String, u32> {
        let chars = compact(text);
        let mut counts: HashMap<String, u32> = HashMap::new();
        if chars.len() >= size {
            for start in 0..=chars.len() - size {
                *counts
                    .entry(chars[start..start + size].iter().collect())
                    .or_default() += 1;
            }
        }
        counts
    }

    /// Assert that one tally reproduces the plain counts, aggregate stats included.
    fn check(text: &str, size: usize) {
        let chars = compact(text);
        let expected = brute(text, size);
        let table = NGramTally::of(&chars, size, usize::MAX);
        let by_gram: HashMap<String, u32> = table.grams.iter().cloned().collect();

        assert_eq!(
            table.total_slots,
            chars.len().saturating_sub(size.saturating_sub(1))
        );
        assert_eq!(table.distinct_grams, expected.len());
        assert_eq!(
            table.repeated_grams,
            expected.values().filter(|count| **count > 1).count()
        );
        assert_eq!(
            table.recycled_slots,
            expected
                .values()
                .filter(|count| **count > 1)
                .map(|count| *count as usize)
                .sum::<usize>()
        );
        assert_eq!(by_gram, expected, "grams for size {size} of {text:?}");
        assert!(
            table
                .grams
                .windows(2)
                .all(|pair| pair[0].1 > pair[1].1
                    || (pair[0].1 == pair[1].1 && pair[0].0 < pair[1].0)),
            "grams are ranked by count, ties in code point order: {:?}",
            table.grams
        );
    }

    #[test]
    fn counts_overlapping_windows() {
        let table = NGramTally::of(&compact("abc"), 2, usize::MAX);
        assert_eq!(table.total_slots, 2);
        assert_eq!(
            table.grams,
            vec![("ab".to_string(), 1), ("bc".to_string(), 1)]
        );
    }

    #[test]
    fn ranks_the_most_frequent_grams_first() {
        let table = NGramTally::of(&compact("ababab"), 2, usize::MAX);
        assert_eq!(table.total_slots, 5);
        assert_eq!(table.distinct_grams, 2);
        assert_eq!(table.repeated_grams, 2);
        assert_eq!(table.recycled_slots, 5);
        assert_eq!(
            table.grams,
            vec![("ab".to_string(), 3), ("ba".to_string(), 2)]
        );
        assert_eq!(
            NGramTally::of(&compact("ababab"), 5, usize::MAX).grams,
            vec![("ababa".to_string(), 1), ("babab".to_string(), 1)]
        );
        assert_eq!(
            NGramTally::of(&compact("ababababab"), 5, usize::MAX).grams,
            vec![("ababa".to_string(), 3), ("babab".to_string(), 3)]
        );
    }

    #[test]
    fn names_only_the_asked_for_number_of_grams() {
        // "abcabcabc" holds three 3-grams: abc three times, bca and cab twice each.
        let named = NGramTally::of(&compact("abcabcabc"), 3, 1);
        assert_eq!(named.grams, vec![("abc".to_string(), 3)]);
        assert_eq!(named.total_slots, 7);
        assert_eq!(named.distinct_grams, 3);
        assert_eq!(
            NGramTally::of(&compact("abcabcabc"), 3, 2).grams,
            vec![("abc".to_string(), 3), ("bca".to_string(), 2)]
        );

        // A count wider than the table is the whole table, and naming none is the counts alone.
        let all = NGramTally::of(&compact("abcabcabc"), 3, 30);
        assert_eq!(all.grams.len(), 3);
        assert_eq!(
            NGramTally::of(&compact("abcabcabc"), 3, 2).grams.as_slice(),
            &all.grams[..2]
        );
        let counts = NGramTally::of(&compact("abcabcabc"), 3, 0);
        assert!(counts.grams.is_empty());
        assert_eq!(
            (
                counts.total_slots,
                counts.distinct_grams,
                counts.repeated_grams
            ),
            (all.total_slots, all.distinct_grams, all.repeated_grams)
        );
    }

    #[test]
    fn reads_every_width_up_to_six() {
        let doubled: String = IDEOGRAPHS.iter().copied().chain(IDEOGRAPHS).collect();
        for text in [
            doubled.as_str(),
            "the quick brown fox jumps over the lazy dog, the quick brown fox",
        ] {
            for size in 1..=MAX_N {
                check(text, size);
            }
        }
    }

    #[test]
    fn drops_whitespace_before_cutting_windows() {
        assert_eq!(compact(" a\nb\tc\u{1c}d "), vec!['a', 'b', 'c', 'd']);
        assert_eq!(
            NGramTally::of(&compact("a b"), 2, usize::MAX).grams,
            vec![("ab".to_string(), 1)]
        );
        assert_eq!(
            NGramTally::of(&compact(" \n\t"), 1, usize::MAX).total_slots,
            0
        );
        assert_eq!(
            NGramTally::of(&compact(""), 5, usize::MAX).grams,
            Vec::<(String, u32)>::new()
        );
    }

    #[test]
    fn handles_a_text_shorter_than_the_window() {
        let table = NGramTally::of(&compact("ab"), 5, usize::MAX);
        assert_eq!(
            (table.size, table.total_slots, table.distinct_grams),
            (5, 0, 0)
        );
        assert!(table.grams.is_empty());
    }

    #[test]
    fn refuses_a_size_the_packing_does_not_hold() {
        assert!(check_size(1).is_ok());
        assert!(check_size(MAX_N).is_ok());
        assert!(check_size(0).is_err());
        assert!(check_size(MAX_N + 1).is_err());
    }

    #[test]
    fn counts_a_pathological_text_once_per_window() {
        let text = "a".repeat(64);
        let table = NGramTally::of(&compact(&text), 5, usize::MAX);
        assert_eq!(table.total_slots, 60);
        assert_eq!(table.distinct_grams, 1);
        assert_eq!(table.recycled_slots, 60);
        assert_eq!(table.grams, vec![("aaaaa".to_string(), 60)]);
    }

    /// The plain per-window recycling of a text: its slots, its windows, and their mean rate.
    fn brute_recycling(text: &str, size: usize, window: usize) -> (usize, usize, f64) {
        let chars = compact(text);
        let total_slots = chars.len().saturating_sub(size.saturating_sub(1));
        let mut spans: Vec<(usize, usize)> = Vec::new();
        let mut start = 0;
        while start + window <= total_slots {
            spans.push((start, window));
            start += window;
        }
        if spans.is_empty() && total_slots > 0 {
            spans.push((0, total_slots));
        }
        let rates: Vec<f64> = spans
            .iter()
            .map(|(start, held)| {
                let span: String = chars[*start..*start + *held + size - 1].iter().collect();
                let recycled: usize = brute(&span, size)
                    .values()
                    .filter(|count| **count > 1)
                    .map(|count| *count as usize)
                    .sum();
                recycled as f64 / *held as f64 * 1000.0
            })
            .collect();
        let mean = if rates.is_empty() {
            0.0
        } else {
            rates.iter().sum::<f64>() / rates.len() as f64
        };
        (total_slots, spans.len(), mean)
    }

    /// Assert that one recycling measure reproduces the plain per-window count.
    fn check_recycling(text: &str, size: usize, window: usize) {
        let chars = compact(text);
        let measured = NGramRecycling::of(&chars, size, window);
        let (total_slots, windows, per_1k) = brute_recycling(text, size, window);
        assert_eq!(
            NGramTally::of(&chars, size, 0).total_slots,
            total_slots,
            "over {text:?} at size {size}"
        );
        assert_eq!(
            measured.windows, windows,
            "over {text:?} at size {size}, window {window}"
        );
        assert!(
            (measured.recycled_per_1k - per_1k).abs() < 1e-9,
            "{} vs {per_1k} over {text:?} at size {size}, window {window}",
            measured.recycled_per_1k
        );
    }

    #[test]
    fn counts_a_window_that_repeats_itself_as_recycled() {
        // "abcabc" holds four 3-grams, of which the two "abc" slots are a repeat.
        let measured = NGramRecycling::of(&compact("abcabc"), 3, 1000);
        assert_eq!(measured.windows, 1);
        assert_eq!(measured.recycled_per_1k, 500.0);
    }

    #[test]
    fn measures_the_recycling_of_every_window_size() {
        let wide: String = IDEOGRAPHS.iter().copied().collect();
        let long = format!("{wide} the quick brown fox jumps over the lazy dog ").repeat(20);
        for size in 1..=MAX_N {
            for window in [1, 7, 64, 1000] {
                check_recycling(&long, size, window);
            }
        }
        check_recycling("", 3, 16);
        check_recycling("  \n\t", 1, 4);
        check_recycling("ab", 5, 4);
        check_recycling("abab", 2, 1000);
        check_recycling("ababababababababab", 2, 6);
    }

    #[test]
    fn measures_a_text_shorter_than_one_window_as_one_window() {
        let measured = NGramRecycling::of(&compact("abab"), 2, 1000);
        assert_eq!(measured.windows, 1);
        assert!((measured.recycled_per_1k - 2000.0 / 3.0).abs() < 1e-9);
        assert_eq!(NGramRecycling::of(&compact("ab"), 5, 1000).windows, 0);
        assert_eq!(NGramRecycling::of(&compact(""), 1, 1).recycled_per_1k, 0.0);
    }

    #[test]
    fn drops_the_trailing_block_shorter_than_one_window() {
        let measured = NGramRecycling::of(&compact("abababababab"), 2, 4);
        assert_eq!(measured.windows, 2);
    }
}
