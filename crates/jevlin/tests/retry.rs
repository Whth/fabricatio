//! The retry policy a caller configures, and the delay it asks for after an attempt fails.

#![cfg(feature = "client")]

use std::time::Duration;

use jevlin::RetryConfig;

#[test]
fn backoff_grows_exponentially_up_to_the_ceiling() {
    let retry = RetryConfig {
        max_attempts: 6,
        initial_backoff: Duration::from_millis(100),
        max_backoff: Duration::from_millis(400),
        backoff_multiplier: 2,
    };

    assert_eq!(retry.backoff(1), Duration::from_millis(100));
    assert_eq!(retry.backoff(2), Duration::from_millis(200));
    assert_eq!(retry.backoff(3), Duration::from_millis(400));
    assert_eq!(retry.backoff(4), Duration::from_millis(400));
    assert_eq!(retry.backoff(64), Duration::from_millis(400));
}

#[test]
fn defaults_to_the_documented_schedule() {
    let retry = RetryConfig::default();

    assert_eq!(retry.max_attempts, 4);
    assert_eq!(retry.initial_backoff, Duration::from_millis(500));
    assert_eq!(retry.max_backoff, Duration::from_secs(8));
    assert_eq!(retry.backoff(1), Duration::from_millis(500));
    assert_eq!(retry.backoff(2), Duration::from_secs(1));
    assert_eq!(retry.backoff(3), Duration::from_secs(2));
}
