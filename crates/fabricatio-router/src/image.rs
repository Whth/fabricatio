//! Attachment preparation for multimodal completion requests.
//!
//! One raw image blob becomes one [`ImageAttachment`]: the digest is taken over the
//! ORIGINAL bytes — the completion cache keys on it, so compression settings never
//! change cache hits — while the data URI carries the payload actually sent, which is
//! a quality-driven lossy re-encode when image compression is enabled.

use std::borrow::Cow;
use std::io::Cursor;

use fabricatio_config::{CONFIG, ImageCompressionConfig, ImageCompressionFormat};
use fabricatio_logger::debug;
use image::codecs::jpeg::JpegEncoder;
use image::imageops::FilterType;
use image::{ImageReader, RgbImage};
use thryd::ImageAttachment;
use thryd::utils::bytes_to_data_uri;

/// Build the wire attachment for one raw image blob.
pub fn attach(bytes: &[u8]) -> ImageAttachment {
    ImageAttachment {
        uri: bytes_to_data_uri(&payload(bytes)),
        digest: blake3::hash(bytes).to_hex().to_string(),
    }
}

/// The bytes actually sent: the original, or the smaller re-encode when compression
/// is enabled and the re-encode pays off.
fn payload(bytes: &[u8]) -> Cow<'_, [u8]> {
    let cfg = &CONFIG.routing.image_compression;
    if !cfg.enabled {
        return Cow::Borrowed(bytes);
    }
    match compressed(bytes, cfg) {
        Some(smaller) => Cow::Owned(smaller),
        None => {
            debug!(
                "Image compression left the payload unchanged ({} bytes)",
                bytes.len()
            );
            Cow::Borrowed(bytes)
        }
    }
}

/// Re-encode `bytes` at the configured quality, or `None` when the payload cannot be
/// decoded or the re-encode would not shrink it.
fn compressed(bytes: &[u8], cfg: &ImageCompressionConfig) -> Option<Vec<u8>> {
    let decoded = ImageReader::new(Cursor::new(bytes))
        .with_guessed_format()
        .ok()?
        .decode()
        .ok()?;
    let scaled = match cfg.max_megapixels {
        Some(mp)
            if decoded.width() as f64 * decoded.height() as f64 > f64::from(mp) * 1_000_000.0 =>
        {
            let scale = (f64::from(mp) * 1_000_000.0
                / (f64::from(decoded.width()) * f64::from(decoded.height())))
            .sqrt();
            decoded.resize(
                ((f64::from(decoded.width()) * scale) as u32).max(1),
                ((f64::from(decoded.height()) * scale) as u32).max(1),
                FilterType::Lanczos3,
            )
        }
        _ => decoded,
    };
    let rgb: RgbImage = scaled.to_rgb8();
    let out = match cfg.format {
        ImageCompressionFormat::Jpeg => {
            let mut out = Vec::new();
            rgb.write_with_encoder(JpegEncoder::new_with_quality(&mut out, cfg.quality))
                .ok()?;
            out
        }
        ImageCompressionFormat::Webp => {
            webp::Encoder::from_rgb(rgb.as_raw(), rgb.width(), rgb.height())
                .encode(f32::from(cfg.quality))
                .to_vec()
        }
    };
    (out.len() < bytes.len()).then_some(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use image::{DynamicImage, ImageFormat, Rgb};

    /// A speckled gradient: cheap to build, but not something a lossy encode keeps whole.
    fn test_png(width: u32, height: u32) -> Vec<u8> {
        let mut img = RgbImage::from_fn(width, height, |x, y| {
            Rgb([(x % 256) as u8, (y % 256) as u8, ((x ^ y) % 256) as u8])
        });
        for (i, pixel) in img.pixels_mut().enumerate() {
            pixel.0[0] = pixel.0[0].wrapping_add((i % 17) as u8);
        }
        let mut out = Vec::new();
        DynamicImage::ImageRgb8(img)
            .write_to(&mut Cursor::new(&mut out), ImageFormat::Png)
            .unwrap();
        out
    }

    fn cfg(
        format: ImageCompressionFormat,
        quality: u8,
        max_megapixels: Option<f32>,
    ) -> ImageCompressionConfig {
        ImageCompressionConfig {
            enabled: true,
            format,
            quality,
            max_megapixels,
        }
    }

    #[test]
    fn jpeg_reencode_shrinks_and_keeps_the_frame() {
        let source = test_png(320, 200);
        let encoded = compressed(&source, &cfg(ImageCompressionFormat::Jpeg, 85, None)).unwrap();
        assert!(encoded.len() < source.len());
        let decoded = image::load_from_memory(&encoded).unwrap();
        assert_eq!((decoded.width(), decoded.height()), (320, 200));
    }

    #[test]
    fn webp_reencode_shrinks() {
        let source = test_png(320, 200);
        let encoded = compressed(&source, &cfg(ImageCompressionFormat::Webp, 80, None)).unwrap();
        assert!(encoded.len() < source.len());
        assert_eq!(&encoded[..4], b"RIFF");
        assert_eq!(image::load_from_memory(&encoded).unwrap().width(), 320);
    }

    #[test]
    fn max_megapixels_caps_the_pixel_count_only_when_larger() {
        let source = test_png(400, 200); // 80,000 px = 0.08 MP
        let capped =
            compressed(&source, &cfg(ImageCompressionFormat::Jpeg, 85, Some(0.04))).unwrap();
        let decoded = image::load_from_memory(&capped).unwrap();
        assert!(decoded.width() * decoded.height() <= 40_000);
        assert!((decoded.width() as f64 / f64::from(decoded.height()) - 2.0).abs() < 0.05);

        let untouched =
            compressed(&source, &cfg(ImageCompressionFormat::Jpeg, 85, Some(1.0))).unwrap();
        assert_eq!(image::load_from_memory(&untouched).unwrap().width(), 400);
    }

    #[test]
    fn a_reencode_that_would_grow_the_payload_is_discarded() {
        let source = test_png(200, 120);
        let lean = compressed(&source, &cfg(ImageCompressionFormat::Jpeg, 50, None)).unwrap();
        assert!(compressed(&lean, &cfg(ImageCompressionFormat::Jpeg, 98, None)).is_none());
    }

    #[test]
    fn undecodable_payloads_are_left_alone() {
        assert!(
            compressed(
                b"not an image",
                &cfg(ImageCompressionFormat::Jpeg, 85, None)
            )
            .is_none()
        );
    }

    #[test]
    fn the_digest_follows_the_original_bytes() {
        let source = test_png(64, 64);
        assert_eq!(
            attach(&source).digest,
            blake3::hash(&source).to_hex().to_string()
        );
    }
}
