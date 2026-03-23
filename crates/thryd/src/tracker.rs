use crate::{BUCKET_COUNT, BUCKETS_WINDOW_S};
use cached::proc_macro::cached;
use std::time::{SystemTime, UNIX_EPOCH};

/// Count tokens in a string using tiktoken
#[cached]
pub fn count_token(string: String) -> u64 {
    tiktoken_rs::o200k_base_singleton()
        .encode_ordinary(string.as_str())
        .len() as u64
}

pub type TimeStamp = u128;

pub type Quota = u64;

#[derive(Default, Debug)]
struct UsageBucket(Quota, TimeStamp);

impl UsageBucket {
    #[inline]
    fn reset(&mut self, timestamp: TimeStamp) -> &mut Self {
        self.set(timestamp, 0)
    }

    #[inline]
    fn set(&mut self, timestamp: TimeStamp, val: Quota) -> &mut Self {
        self.1 = timestamp;
        self.0 = val;

        self
    }

    fn expired(&mut self, timestamp: TimeStamp) -> &mut Self {
        if (timestamp - BUCKETS_WINDOW_S as TimeStamp) > self.1 {
            self.reset(timestamp)
        } else {
            self
        }
    }

    fn valid(&self, timestamp: TimeStamp) -> Option<&Self> {
        ((timestamp - BUCKETS_WINDOW_S as TimeStamp) <= self.1).then_some(self)
    }

    fn add_one(&mut self, timestamp: TimeStamp) {
        self.add(1, timestamp)
    }

    fn add(&mut self, val: u64, timestamp: TimeStamp) {
        self.expired(timestamp).set(timestamp, val);
    }
}

#[derive(Debug)]
struct UsageBuckets {
    buckets: [UsageBucket; BUCKET_COUNT],
    quota: Quota,
}

impl UsageBuckets {
    fn with_quota(quota: u64) -> Self {
        Self {
            quota,
            ..Self::default()
        }
    }

    fn get_bucket_mut(&mut self, timestamp: &TimeStamp) -> &mut UsageBucket {
        self.buckets
            .get_mut(((timestamp / 1000) % BUCKET_COUNT as TimeStamp) as usize)
            .unwrap()
    }

    fn used(&self, cur_timestamp: TimeStamp) -> Quota {
        self.buckets
            .iter()
            .filter_map(|e| e.valid(cur_timestamp))
            .map(|e| e.0)
            .sum()
    }

    fn remaining_quota(&self, cur_timestamp: TimeStamp) -> Quota {
        self.quota - self.used(cur_timestamp)
    }

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

    /// Calculates the minimum cooldown time required to accommodate the input token.
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

/// Tracks API usage within a sliding time window for quota management.
#[derive(Default, Debug)]
pub struct UsageTracker {
    rpm_buckets: Option<UsageBuckets>,
    tpm_buckets: Option<UsageBuckets>,
}

impl UsageTracker {
    pub fn with_quota(tpm_quota: Option<Quota>, rpm_quota: Option<Quota>) -> Self {
        Self {
            tpm_buckets: tpm_quota.map(UsageBuckets::with_quota),
            rpm_buckets: rpm_quota.map(UsageBuckets::with_quota),
        }
    }

    /// Record a request with token counts
    pub fn add_request(&mut self, used_token: Quota) -> &mut Self {
        let timestamp = self.current_timestamp();

        if let Some(rpm_b) = self.rpm_buckets.as_mut() {
            rpm_b.get_bucket_mut(&timestamp).add_one(timestamp);
        }

        if let Some(tpm_b) = self.tpm_buckets.as_mut() {
            tpm_b.get_bucket_mut(&timestamp).add(used_token, timestamp);
        }

        self
    }

    pub fn add_request_raw(&mut self, input_text: String, output_text: String) -> &mut Self {
        self.add_request(count_token(input_text) + count_token(output_text))
    }

    /// Get total requests in current window
    pub fn rpm_usage(&self) -> Option<Quota> {
        self.rpm_buckets
            .as_ref()
            .map(|q| q.used(self.current_timestamp()))
    }

    pub fn remaining_rpm_quota(&self) -> Option<Quota> {
        self.rpm_buckets
            .as_ref()
            .map(|q| q.remaining_quota(self.current_timestamp()))
    }

    /// Get total tokens in current window
    pub fn tpm_usage(&self) -> Option<Quota> {
        self.tpm_buckets
            .as_ref()
            .map(|q| q.used(self.current_timestamp()))
    }

    pub fn remaining_tpm_quota(&self) -> Option<Quota> {
        self.tpm_buckets
            .as_ref()
            .map(|q| q.remaining_quota(self.current_timestamp()))
    }

    fn current_timestamp(&self) -> TimeStamp {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("Time went backwards")
            .as_millis()
    }

    pub fn need_wait_for(&self, input_token: Quota) -> u64 {
        let cur = self.current_timestamp();
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

    pub fn need_wait_for_string(&self, input_string: String) -> u64 {
        self.need_wait_for(count_token(input_string))
    }

    pub fn has_capacity(&self) -> bool {
        self.remaining_rpm_quota().unwrap_or(1) > 0 && self.remaining_tpm_quota().unwrap_or(1) > 0
    }
}

#[cfg(test)]
mod tests {}
