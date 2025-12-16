use error_mapping::AsPyErr;
use pyo3::prelude::*;
use std::fs::File;
use std::io::{self, Read};
use std::path::{Path, PathBuf};

/// Heuristic configuration for detecting whether a file is likely text.
#[derive(Clone, Copy, Debug)]
pub struct TextHeuristic {
    /// Number of bytes to sample from the start of the file (e.g., 1024).
    /// Larger values improve accuracy but reduce speed.
    pub sample_size: usize,

    /// If `false`, any null byte (`\0`) immediately classifies the file as binary.
    /// Most plain text files (UTF-8, ASCII) do not contain null bytes.
    pub allow_null: bool,

    /// Maximum allowed ratio of "non-printable control characters" (excluding `\t`, `\n`, `\r`).
    /// Valid range: `0.0` (strict) to `1.0` (accept anything).
    /// Example: `0.1` means up to 10% of sampled bytes may be control chars.
    pub control_char_threshold: f32,
}

impl Default for TextHeuristic {
    fn default() -> Self {
        Self {
            sample_size: 1024,
            allow_null: false,
            control_char_threshold: 0.3,
        }
    }
}

/// Determines if a file is likely a text file using configurable heuristics.
///
/// This function:
/// - Reads only the first `sample_size` bytes.
/// - Uses stack-allocated buffer (no heap allocation).
/// - Exits early on null byte (if disallowed) or control-char threshold breach.
/// - Avoids UTF-8 validation for maximum speed.
///
/// ⚠️ This is a heuristic — not 100% accurate, but extremely fast.
pub fn is_text<P: AsRef<Path>>(path: P, heuristic: &TextHeuristic) -> io::Result<bool> {
    if !path.as_ref().exists() || path.as_ref().is_dir() {
        return Ok(false);
    }

    if heuristic.sample_size == 0 {
        return Ok(true); // Treat zero-sample as text
    }

    let mut file = File::open(path)?;
    // Use a fixed max buffer on the stack (8KB max sample)
    let mut buffer = [0u8; 8192];

    let read_len = heuristic.sample_size.min(buffer.len());
    let n = file.read(&mut buffer[..read_len])?;

    if n == 0 {
        return Ok(true); // Empty files are considered text
    }

    let data = &buffer[..n];

    // Fast null-byte check (strong binary signal)
    if !heuristic.allow_null && data.contains(&0) {
        return Ok(false);
    }

    // Fast path: if threshold is 0, reject on any control char
    if heuristic.control_char_threshold <= 0.0 {
        return Ok(!data.iter().any(|&b| is_strict_control_char(b)));
    }

    // Count "bad" control characters (excluding \t, \n, \r)
    let mut control_count = 0;
    let threshold_count = (heuristic.control_char_threshold * n as f32).ceil() as usize;

    for &b in data {
        if is_strict_control_char(b) {
            control_count += 1;
            // Early exit: exceeds allowed ratio
            if control_count > threshold_count {
                return Ok(false);
            }
        }
    }

    Ok(true)
}

/// Returns `true` if the byte is a non-printable control character,
/// excluding tab (`\t`), line feed (`\n`), and carriage return (`\r`).
#[inline(always)]
fn is_strict_control_char(b: u8) -> bool {
    matches!(b,
        0x00..=0x08   // Null through backspace (excl. \t = 0x09)
        | 0x0B        // Vertical tab
        | 0x0C        // Form feed
        | 0x0E..=0x1F // Shift out through unit separator (excl. \r = 0x0D)
        | 0x7F        // DEL
    )
}

#[pyfunction]
/// judge if a file is likely text, dir or path not exist are considered false.
pub fn is_likely_text(path: PathBuf) -> PyResult<bool> {
    is_text(path, &TextHeuristic::default()).into_pyresult()
}

pub(crate) fn register(_py: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(is_likely_text, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::TempDir;

    fn create_temp_file(contents: &[u8]) -> PathBuf {
        let dir = TempDir::new().unwrap();
        let path = dir.path().join("testfile");
        let mut file = File::create(&path).unwrap();
        file.write_all(contents).unwrap();
        // Keep dir alive by leaking (for simplicity in tests)
        std::mem::forget(dir);
        path
    }

    #[test]
    fn test_empty_file_is_text() {
        let path = create_temp_file(&[]);
        assert!(is_text(&path, &TextHeuristic::default()).unwrap());
    }

    #[test]
    fn test_null_byte_rejects_by_default() {
        let path = create_temp_file(b"Hello\0World");
        assert!(!is_text(&path, &TextHeuristic::default()).unwrap());
    }

    #[test]
    fn test_allow_null_accepts_null_bytes() {
        let heuristic = TextHeuristic {
            allow_null: true,
            ..TextHeuristic::default()
        };
        let path = create_temp_file(b"Hello\0World");
        assert!(is_text(&path, &heuristic).unwrap());
    }

    #[test]
    fn test_control_char_threshold_zero_rejects_any_control() {
        let heuristic = TextHeuristic {
            control_char_threshold: 0.0,
            ..TextHeuristic::default()
        };
        let path = create_temp_file(b"Hello\x01World"); // SOH is control char
        assert!(!is_text(&path, &heuristic).unwrap());
    }

    #[test]
    fn test_control_char_within_threshold() {
        // 10 bytes, 2 control chars → 20% → below 30% default threshold
        let data = b"\x01\x02abcdefgh";
        let path = create_temp_file(data);
        assert!(is_text(&path, &TextHeuristic::default()).unwrap());
    }

    #[test]
    fn test_control_char_exceeds_threshold() {
        // 10 bytes, 4 control chars → 40% > 30% threshold → binary
        let data = b"\x01\x02\x03\x04abcdef";
        let path = create_temp_file(data);
        assert!(!is_text(&path, &TextHeuristic::default()).unwrap());
    }

    #[test]
    fn test_tabs_and_newlines_are_not_control_chars() {
        let data = b"Line 1\nLine 2\r\n\tIndented";
        let path = create_temp_file(data);
        assert!(is_text(&path, &TextHeuristic::default()).unwrap());
    }

    #[test]
    fn test_del_char_is_control() {
        let data = b"Hello\x7f\x7f\x7f\x7f\x7f\x7f\x7f";
        let path = create_temp_file(data);
        assert!(!is_text(&path, &TextHeuristic::default()).unwrap());
    }

    #[test]
    fn test_zero_sample_size_considered_text() {
        let heuristic = TextHeuristic {
            sample_size: 0,
            ..TextHeuristic::default()
        };

        let path = create_temp_file(b"\x00\x01\x02");
        assert!(is_text(&path, &heuristic).unwrap());
    }

    #[test]
    fn test_large_sample_size_truncated_to_buffer() {
        // Internal buffer is 8192, so this should still work
        let heuristic = TextHeuristic {
            sample_size: 16384,
            ..TextHeuristic::default()
        };

        let text = "A".repeat(10000).into_bytes();
        let path = create_temp_file(&text);
        assert!(is_text(&path, &heuristic).unwrap());
    }

    #[test]
    fn test_utf8_non_ascii_text() {
        let data = "你好，世界！\nThis is UTF-8 🌍".as_bytes();
        let path = create_temp_file(data);
        assert!(is_text(&path, &TextHeuristic::default()).unwrap());
    }

    #[test]
    fn test_vertical_tab_and_form_feed_are_control_chars() {
        // \x0B = VT, \x0C = FF
        let data = b"\x0B\x0Cd";
        let path = create_temp_file(data);
        assert!(!is_text(&path, &TextHeuristic::default()).unwrap());
    }
}
