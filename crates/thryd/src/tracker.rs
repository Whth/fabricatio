use crate::constants::{MAX_BUFFER_SIZE, MINITE_MS, MIN_BUFFER_SIZE};
use cached::proc_macro::cached;
use std::collections::VecDeque;
use std::time::{SystemTime, UNIX_EPOCH};

/// Count tokens in a string using tiktoken
#[cached]
pub fn count_token(string: String) -> u32 {
    tiktoken_rs::o200k_base_singleton()
        .encode_ordinary(string.as_str())
        .len() as u32
}

/// Records token usage and timestamp for a single API request
#[derive(Debug, Clone)]
pub struct RequestInfo {
    pub input_token: u32,
    pub output_token: u32,
    pub timestamp: u64,
}

impl RequestInfo {
    /// Returns total tokens used in this request
    pub fn total_token(&self) -> u32 {
        self.input_token + self.output_token
    }
}

/// Tracks API usage within a sliding time window for quota management.
pub struct UsageTracker {
    request_infos: VecDeque<RequestInfo>,
    window_size_ms: u64,
    request_quota: Option<u32>,
    token_quota: Option<u32>,
}

impl UsageTracker {
    /// Create a new tracker with token and request quotas
    pub fn new(token_quota: u32, request_quota: u32, window_size_ms: u64) -> Self {
        Self {
            token_quota: Some(token_quota),
            request_quota: Some(request_quota),
            window_size_ms,
            ..Self::default()
        }
    }


    /// Create tracker with quotas (default 60s window)
    pub fn with_quota(tpm_quota: Option<u32>, rpm_quota: Option<u32>) -> Self {
        Self {
            token_quota: tpm_quota,
            request_quota: rpm_quota,
            ..Self::default()
        }
    }

    /// Create tracker with custom window size
    pub fn with_window_size(window_size_ms: u64) -> Self {
        Self {
            window_size_ms,
            ..Self::default()
        }
    }


    /// Record a request with token counts
    pub fn add_request(&mut self, input_token: u32, output_token: u32) -> &mut Self {
        let timestamp = self.current_timestamp();
        self.request_infos.push_back(RequestInfo {
            input_token,
            output_token,
            timestamp,
        });

        if self.request_infos.len() > MAX_BUFFER_SIZE {
            self.request_infos.pop_front();
        }

        self
    }


    pub fn add_request_raw(&mut self, input_text: String, output_text: String) -> &mut Self {
        self.add_request(count_token(input_text), count_token(output_text))
    }

    /// Get total requests in current window
    pub fn request_usage(&self) -> u32 {
        self.window_requests().len() as u32
    }

    /// Get total tokens in current window
    pub fn token_usage(&self) -> u64 {
        self.window_requests()
            .iter()
            .map(|req| req.total_token() as u64)
            .sum()
    }

    /// Get window size in ms
    pub fn window_size_ms(&self) -> u64 {
        self.window_size_ms
    }

    /// Get request quota
    pub fn request_quota(&self) -> Option<u32> {
        self.request_quota
    }

    /// Get token quota
    pub fn token_quota(&self) -> Option<u32> {
        self.token_quota
    }

    /// Get remaining requests allowed
    pub fn remaining_requests(&self) -> Option<u32> {
        self.request_quota.map(|q| q.saturating_sub(self.request_usage()))
    }

    /// Get remaining tokens allowed
    pub fn remaining_tokens(&self) -> Option<u64> {
        self.token_quota.map(|q| (q as u64).saturating_sub(self.token_usage()))
    }

    /// Alias for remaining_requests
    pub fn remaining_rpm(&self) -> Option<u32> {
        self.remaining_requests()
    }

    /// Alias for remaining_tokens
    pub fn remaining_tpm(&self) -> Option<u64> {
        self.remaining_tokens()
    }


    /// Check if request can be made with given input tokens
    pub fn can_make_request(&self, input_tokens: u32) -> bool {
        let req_ok = self.request_quota
            .is_none_or(|q| self.request_usage() < q);

        let token_ok = self.token_quota
            .is_none_or(|q| (self.token_usage() as u32).saturating_add(input_tokens) <= q);

        req_ok && token_ok
    }

    /// Estimate wait time for given input tokens
    pub fn estimated_waiting_time_for_tokens(&self, input_tokens: u32) -> u64 {
        let in_window = self.window_requests();
        let current_ts = self.current_timestamp();

        let req_wait = self.calculate_request_wait_time(&in_window, current_ts);
        let token_wait = self.calculate_token_wait_time(&in_window, input_tokens, current_ts);

        req_wait.max(token_wait)
    }

    fn calculate_request_wait_time(&self, in_window: &[&RequestInfo], current_ts: u64) -> u64 {
        self.request_quota.map_or(0, |q| {
            let usage = in_window.len() as u32;
            if usage < q {
                0
            } else {
                let idx = (usage - q) as usize;
                in_window.get(idx).map_or(0, |req| {
                    (req.timestamp + self.window_size_ms).saturating_sub(current_ts)
                })
            }
        })
    }

    fn calculate_token_wait_time(
        &self,
        in_window: &[&RequestInfo],
        input_tokens: u32,
        current_ts: u64,
    ) -> u64 {
        self.token_quota.map_or(0, |q| {
            let usage: u32 = in_window.iter().map(|req| req.total_token()).sum();

            if usage.saturating_add(input_tokens) <= q {
                return 0;
            }

            let excess = usage.saturating_add(input_tokens) - q;

            in_window
                .iter()
                .scan(0u32, |released, req| {
                    *released = released.saturating_add(req.total_token());
                    Some((*released, req))
                })
                .find(|(released, _)| *released >= excess)
                .map(|(_, req)| (req.timestamp + self.window_size_ms).saturating_sub(current_ts))
                .unwrap_or(0)
        })
    }

    // ============== Private helpers ==============

    fn current_timestamp(&self) -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("Time went backwards")
            .as_millis() as u64
    }

    fn window_start(&self) -> u64 {
        self.current_timestamp().saturating_sub(self.window_size_ms)
    }

    fn window_requests(&self) -> Vec<&RequestInfo> {
        let start = self.window_start();
        self.request_infos
            .iter()
            .skip_while(|req| req.timestamp < start)
            .collect()
    }
}

impl Default for UsageTracker {
    fn default() -> Self {
        Self {
            request_infos: VecDeque::with_capacity(MIN_BUFFER_SIZE),
            window_size_ms: MINITE_MS,
            request_quota: None,
            token_quota: None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_info(input: u32, output: u32, ts: u64) -> RequestInfo {
        RequestInfo { input_token: input, output_token: output, timestamp: ts }
    }

    fn fill(tracker: &mut UsageTracker, reqs: Vec<RequestInfo>) {
        tracker.request_infos.clear();
        for r in reqs {
            tracker.request_infos.push_back(r);
        }
    }

    #[test]
    fn test_default() {
        let t = UsageTracker::default();
        assert_eq!(t.window_size_ms, 60_000);
        assert!(t.request_quota.is_none());
        assert!(t.token_quota.is_none());
    }

    #[test]
    fn test_new() {
        let t = UsageTracker::new(1000, 60, 60_000);
        assert_eq!(t.token_quota, Some(1000));
        assert_eq!(t.request_quota, Some(60));
    }

    #[test]
    fn test_add_request() {
        let mut t = UsageTracker::default();
        t.add_request(100, 50);
        assert_eq!(t.request_infos.len(), 1);
        assert_eq!(t.request_usage(), 1);
    }

    #[test]
    fn test_can_make_request() {
        let mut t = UsageTracker::with_quota(Some(100), Some(5));
        assert!(t.can_make_request(50)); // 50 tokens, 1 request

        // Exhaust quota
        for _ in 0..5 {
            t.add_request(10, 0);
        }

        assert!(!t.can_make_request(50)); // Would exceed request quota
    }

    #[test]
    fn test_remaining() {
        let mut t = UsageTracker::with_quota(Some(100), Some(3));
        assert_eq!(t.remaining_requests(), Some(3));
        assert_eq!(t.remaining_tokens(), Some(100));

        t.add_request(30, 0);

        assert_eq!(t.remaining_requests(), Some(2));
        assert_eq!(t.remaining_tokens(), Some(70));
    }

    #[test]
    fn test_window_expiry() {
        let mut t = UsageTracker::with_window_size(1000);
        let now = t.current_timestamp();

        fill(&mut t, vec![
            create_info(10, 5, now - 2000),
            create_info(10, 5, now - 500),
        ]);

        assert_eq!(t.request_usage(), 1); // Only one in window
    }

    #[test]
    fn test_request_info_total() {
        let info = RequestInfo { input_token: 100, output_token: 50, timestamp: 0 };
        assert_eq!(info.total_token(), 150);
    }
}
