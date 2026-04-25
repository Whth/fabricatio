use crate::utils::{TimeStamp, current_timestamp};
use crate::{BUCKET_COUNT, BUCKETS_WINDOW_S};
use cached::proc_macro::cached;

/// Counts tokens in a string using tiktoken's o200k_base encoding.
///
/// This function is memoized via the `#[cached]` attribute, meaning repeated calls
/// with the same input string will return the cached result without recomputing.
///
/// # Arguments
/// * `string` - The text string to count tokens for
///
/// # Returns
/// * `u64` - The number of tokens in the string
///
/// # Example
/// ```rust
/// use thryd::tracker::count_token;
///
/// let tokens = count_token("Hello, world!".to_string());
/// println!("Token count: {}", tokens);
/// ```
#[cached]
pub fn count_token(string: String) -> u64 {
    tiktoken_rs::o200k_base_singleton()
        .encode_ordinary(string.as_str())
        .len() as u64
}

/// A quota value representing either requests-per-minute (RPM) or tokens-per-minute (TPM).
///
/// This is a type alias for `u64`, distinguishing quota values from other numeric types
/// in the codebase.
pub type Quota = u64;

/// A single time bucket in the sliding window rate limiting algorithm.
///
/// Each bucket tracks usage for a specific 1-second interval. Buckets expire
/// after `BUCKETS_WINDOW_S` seconds (default 60 seconds), implementing a
/// sliding window counter for accurate rate limiting.
///
/// A bucket is valid if its timestamp is within the current window.
#[derive(Default, Debug)]
struct UsageBucket(Quota, TimeStamp);

impl UsageBucket {
    /// Resets the bucket to zero usage at the given timestamp.
    ///
    /// Called when a bucket expires and needs to be reused.
    #[inline]
    fn reset(&mut self, timestamp: TimeStamp) -> &mut Self {
        self.set(timestamp, 0)
    }

    /// Sets the bucket's timestamp and quota value.
    #[inline]
    fn set(&mut self, timestamp: TimeStamp, val: Quota) -> &mut Self {
        self.1 = timestamp;
        self.0 = val;

        self
    }

    /// Expires the bucket if it's outside the sliding window.
    ///
    /// A bucket is considered expired if its timestamp is older than
    /// `BUCKETS_WINDOW_S` milliseconds from the current timestamp.
    fn expired(&mut self, timestamp: TimeStamp) -> &mut Self {
        if (timestamp - BUCKETS_WINDOW_S as TimeStamp) > self.1 {
            self.reset(timestamp)
        } else {
            self
        }
    }

    /// Returns `Some(self)` if the bucket is still valid (within the window),
    /// or `None` if the bucket has expired.
    fn valid(&self, timestamp: TimeStamp) -> Option<&Self> {
        ((timestamp - BUCKETS_WINDOW_S as TimeStamp) <= self.1).then_some(self)
    }

    /// Increments the bucket usage by 1.
    fn add_one(&mut self, timestamp: TimeStamp) {
        self.add(1, timestamp)
    }

    /// Adds a quota amount to this bucket, first expiring it if necessary.
    fn add(&mut self, val: u64, timestamp: TimeStamp) {
        self.expired(timestamp).set(timestamp, val);
    }
}

/// A collection of time buckets implementing sliding window rate limiting.
///
/// `UsageBuckets` manages `BUCKET_COUNT` individual buckets (default: 60),
/// each representing a 1-second slot in a 60-second sliding window. This
/// provides more accurate rate limiting than simple fixed windows.
///
/// The implementation uses a tuple struct `(Quota, TimeStamp)` where:
/// - `Quota` is the cumulative usage for requests/tokens in that bucket
/// - `TimeStamp` is when the bucket was last updated
#[derive(Debug)]
struct UsageBuckets {
    /// Array of time buckets covering the sliding window.
    buckets: [UsageBucket; BUCKET_COUNT],
    /// The maximum quota allowed within the sliding window.
    quota: Quota,
}

impl UsageBuckets {
    /// Creates a new `UsageBuckets` with the specified quota limit.
    ///
    /// # Arguments
    /// * `quota` - The maximum allowed usage within the window
    fn with_quota(quota: u64) -> Self {
        Self {
            quota,
            ..Self::default()
        }
    }

    /// Returns a mutable reference to the bucket for a given timestamp.
    ///
    /// The bucket index is calculated via `(timestamp / 1000) % BUCKET_COUNT`,
    /// mapping millisecond timestamps to 1-second bucket slots.
    fn get_bucket_mut(&mut self, timestamp: &TimeStamp) -> &mut UsageBucket {
        self.buckets
            .get_mut(((timestamp / 1000) % BUCKET_COUNT as TimeStamp) as usize)
            .unwrap()
    }

    /// Calculates total usage across all valid buckets in the current window.
    ///
    /// # Arguments
    /// * `cur_timestamp` - Current timestamp in milliseconds
    ///
    /// # Returns
    /// * `Quota` - Sum of usage from all non-expired buckets
    fn used(&self, cur_timestamp: TimeStamp) -> Quota {
        self.buckets
            .iter()
            .filter_map(|e| e.valid(cur_timestamp))
            .map(|e| e.0)
            .sum()
    }

    /// Calculates remaining quota available in the current window.
    ///
    /// # Arguments
    /// * `cur_timestamp` - Current timestamp in milliseconds
    ///
    /// # Returns
    /// * `Quota` - Remaining quota (total quota minus used)
    fn remaining_quota(&self, cur_timestamp: TimeStamp) -> Quota {
        self.quota - self.used(cur_timestamp)
    }

    /// Returns all valid (non-expired) buckets sorted by timestamp.
    ///
    /// Used internally to calculate cooldown times when quota is exceeded.
    fn all_valid(&self, timestamp: TimeStamp) -> Vec<&UsageBucket> {
        let mut seq: Vec<&UsageBucket> = self
            .buckets
            .as_ref()
            .iter()
            .filter_map(|e| e.valid(timestamp))
            .collect();
        seq.sort_by_key(|e| e.1);
        seq
    }

    /// Calculates the minimum milliseconds to wait before the given input token
    /// quota can be accommodated.
    ///
    /// This is used for rate limit backoff calculation. When a request would
    /// exceed quota, this returns the time until sufficient quota becomes available.
    ///
    /// # Arguments
    /// * `input_token` - The token quota needed for the request
    /// * `cur_timestamp` - Current timestamp in milliseconds
    ///
    /// # Returns
    /// * `u64` - Milliseconds to wait; returns `BUCKETS_WINDOW_S * 1000` if no valid buckets
    ///   can accommodate the request (worst case wait time)
    fn min_cooldown_time_for(&self, input_token: Quota, cur_timestamp: TimeStamp) -> Quota {
        let remaining: u64 = self.remaining_quota(cur_timestamp);

        if input_token <= remaining {
            return 0;
        }

        let mut needed: u64 = input_token - remaining;
        let valid_buckets: Vec<&UsageBucket> = self.all_valid(cur_timestamp);

        for bucket in valid_buckets {
            let usage: u64 = bucket.0;

            if usage >= needed {
                let expire_time: TimeStamp = bucket.1 + BUCKETS_WINDOW_S as TimeStamp;
                let wait_time: TimeStamp = expire_time.saturating_sub(cur_timestamp);
                return wait_time as u64;
            } else {
                needed -= usage;
            }
        }

        (BUCKETS_WINDOW_S * 1000) as u64
    }
}

impl Default for UsageBuckets {
    fn default() -> Self {
        Self {
            buckets: core::array::from_fn(|_| UsageBucket::default()),
            quota: 0,
        }
    }
}

/// Tracks API usage using a sliding window algorithm for accurate quota management.
///
/// `UsageTracker` monitors both requests-per-minute (RPM) and tokens-per-minute (TPM)
/// usage against configured quotas. It uses a bucket-based sliding window approach
/// where each bucket represents a 1-second slot, providing more accurate rate limit
/// tracking than traditional fixed-window counters.
///
/// # Sliding Window Algorithm
/// The tracker maintains `BUCKET_COUNT` buckets (default: 60), each covering a 1-second
/// window. When checking usage or calculating backoff times, only buckets within the
/// last `BUCKETS_WINDOW_S` seconds (default: 60) are considered valid.
///
/// # Example
/// ```rust
/// use thryd::tracker::{UsageTracker, count_token};
///
/// let mut tracker = UsageTracker::with_quota(
///     Some(100_000),  // TPM quota
///     Some(60),       // RPM quota
/// );
///
/// // Add a request (input + output tokens)
/// tracker.add_request_raw(
///     "Hello, world!".to_string(),
///     "Hi there!".to_string(),
/// );
///
/// // Check remaining quota
/// let remaining_tpm = tracker.remaining_tpm_quota();
/// let remaining_rpm = tracker.remaining_rpm_quota();
///
/// // Check if we can make another request
/// if tracker.has_capacity() {
///     println!("Can make request immediately");
/// } else {
///     let wait_ms = tracker.need_wait_for_string("Another request".to_string());
///     println!("Wait {}ms", wait_ms);
/// }
/// ```
///
/// # Thread Safety
/// `UsageTracker` uses interior mutability and is not `Sync`. For multi-threaded
/// usage, wrap in a mutex or use within a single-threaded context.
#[derive(Default, Debug)]
pub struct UsageTracker {
    /// RPM tracking buckets, `None` if RPM quota is unlimited
    rpm_buckets: Option<UsageBuckets>,
    /// TPM tracking buckets, `None` if TPM quota is unlimited
    tpm_buckets: Option<UsageBuckets>,
}

impl UsageTracker {
    /// Creates a new `UsageTracker` with the specified quotas.
    ///
    /// Pass `None` for a quota type to disable tracking for that dimension.
    ///
    /// # Arguments
    /// * `tpm_quota` - Tokens-per-minute quota limit, or `None` to disable TPM tracking
    /// * `rpm_quota` - Requests-per-minute quota limit, or `None` to disable RPM tracking
    ///
    /// # Example
    /// ```rust
    /// use thryd::tracker::UsageTracker;
    ///
    /// // Track both RPM and TPM
    /// let tracker = UsageTracker::with_quota(Some(100_000), Some(60));
    ///
    /// // Track only TPM (unlimited RPM)
    /// let tracker = UsageTracker::with_quota(Some(100_000), None);
    /// ```
    pub fn with_quota(tpm_quota: Option<Quota>, rpm_quota: Option<Quota>) -> Self {
        Self {
            tpm_buckets: tpm_quota.map(UsageBuckets::with_quota),
            rpm_buckets: rpm_quota.map(UsageBuckets::with_quota),
        }
    }

    /// Records a request with a pre-counted token amount.
    ///
    /// This increments the RPM counter by 1 and adds `used_token` to the TPM counter.
    ///
    /// # Arguments
    /// * `used_token` - The number of tokens used by this request (input + output)
    ///
    /// # Returns
    /// * `&mut Self` - Returns `self` for method chaining
    pub fn add_request(&mut self, used_token: Quota) -> &mut Self {
        let timestamp = current_timestamp();

        if let Some(rpm_b) = self.rpm_buckets.as_mut() {
            rpm_b.get_bucket_mut(&timestamp).add_one(timestamp);
        }

        if let Some(tpm_b) = self.tpm_buckets.as_mut() {
            tpm_b.get_bucket_mut(&timestamp).add(used_token, timestamp);
        }

        self
    }

    /// Records a request by automatically counting tokens in the input and output text.
    ///
    /// This is a convenience method that calls `count_token()` on both strings and
    /// then calls `add_request()` with the sum.
    ///
    /// # Arguments
    /// * `input_text` - The input/prompt text sent to the model
    /// * `output_text` - The model's response text
    ///
    /// # Returns
    /// * `&mut Self` - Returns `self` for method chaining
    ///
    /// # Example
    /// ```rust
    /// use thryd::tracker::UsageTracker;
    ///
    /// let mut tracker = UsageTracker::with_quota(Some(100_000), Some(60));
    /// tracker.add_request_raw(
    ///     "What is the capital of France?".to_string(),
    ///     "The capital of France is Paris.".to_string(),
    /// );
    /// ```
    pub fn add_request_raw(&mut self, input_text: String, output_text: String) -> &mut Self {
        self.add_request(count_token(input_text) + count_token(output_text))
    }

    /// Returns the total number of requests in the current sliding window.
    ///
    /// # Returns
    /// * `Option<Quota>` - Current RPM usage, or `None` if RPM tracking is disabled
    pub fn rpm_usage(&self) -> Option<Quota> {
        self.rpm_buckets
            .as_ref()
            .map(|q| q.used(current_timestamp()))
    }

    /// Returns the remaining request quota available in the current window.
    ///
    /// # Returns
    /// * `Option<Quota>` - Remaining RPM quota, or `None` if RPM tracking is disabled
    pub fn remaining_rpm_quota(&self) -> Option<Quota> {
        self.rpm_buckets
            .as_ref()
            .map(|q| q.remaining_quota(current_timestamp()))
    }

    /// Returns the total number of tokens used in the current sliding window.
    ///
    /// # Returns
    /// * `Option<Quota>` - Current TPM usage, or `None` if TPM tracking is disabled
    pub fn tpm_usage(&self) -> Option<Quota> {
        self.tpm_buckets
            .as_ref()
            .map(|q| q.used(current_timestamp()))
    }

    /// Returns the remaining token quota available in the current window.
    ///
    /// # Returns
    /// * `Option<Quota>` - Remaining TPM quota, or `None` if TPM tracking is disabled
    pub fn remaining_tpm_quota(&self) -> Option<Quota> {
        self.tpm_buckets
            .as_ref()
            .map(|q| q.remaining_quota(current_timestamp()))
    }

    /// Calculates the minimum wait time needed before a request with the given
    /// token count can be made without violating rate limits.
    ///
    /// This considers both RPM and TPM limits, returning the maximum wait time
    /// required by either constraint.
    ///
    /// # Arguments
    /// * `input_token` - Number of tokens in the incoming request
    ///
    /// # Returns
    /// * `u64` - Milliseconds to wait before the request can proceed.
    ///   Returns 0 if there is sufficient capacity.
    pub fn need_wait_for(&self, input_token: Quota) -> u64 {
        let cur = current_timestamp();
        self.rpm_buckets
            .as_ref()
            .map(|e| e.min_cooldown_time_for(input_token, cur))
            .unwrap_or_default()
            .max(
                self.tpm_buckets
                    .as_ref()
                    .map(|e| e.min_cooldown_time_for(1, cur))
                    .unwrap_or_default(),
            )
    }

    /// Calculates wait time for a request with text that will be token-counted first.
    ///
    /// Convenience method that counts tokens in the input string and calls
    /// `need_wait_for()` with the result.
    ///
    /// # Arguments
    /// * `input_string` - The input text to count tokens for
    ///
    /// # Returns
    /// * `u64` - Milliseconds to wait before the request can proceed
    pub fn need_wait_for_string(&self, input_string: String) -> u64 {
        self.need_wait_for(count_token(input_string))
    }

    /// Checks whether there is capacity to make a request without rate limiting.
    ///
    /// This is a convenience check that verifies both RPM and TPM have remaining quota.
    ///
    /// # Returns
    /// * `bool` - `true` if at least 1 RPM and 1 TPM quota remain, `false` otherwise.
    ///   Returns `true` if the respective tracking is disabled (`None` quota).
    pub fn has_capacity(&self) -> bool {
        self.remaining_rpm_quota().unwrap_or(1) > 0 && self.remaining_tpm_quota().unwrap_or(1) > 0
    }
}

#[cfg(test)]
mod tests {}
