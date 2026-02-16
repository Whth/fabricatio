use crate::constants::{MAX_BUFFER_SIZE, MINITE_MS, MIN_BUFFER_SIZE};
use cached::proc_macro::cached;
use std::collections::VecDeque;
use std::time::{SystemTime, UNIX_EPOCH};

#[cached]
fn count_token(string: String) -> u32 {
    tiktoken_rs::o200k_base_singleton()
        .encode_ordinary(string.as_str())
        .len() as u32
}

/// Records token usage and timestamp for a single API request
#[derive(Debug, Clone)]
pub struct RequestInfo {
    input_token: u32,
    output_token: u32,
    timestamp: u64, // Unix timestamp in milliseconds
}

impl RequestInfo {
    /// Returns total tokens used in this request
    fn total_token(&self) -> u32 {
        self.input_token + self.output_token
    }
}

/// Tracks API usage within a sliding time window for quota management.
///
/// Maintains a queue of past requests and provides methods to check
/// current usage against request-per-window and token-per-window quotas.
/// The window size is configurable (default 60 seconds).
#[derive(Debug)]
pub struct UsageTracker {
    request_infos: VecDeque<RequestInfo>,
    window_size_ms: u64,
    request_quota: Option<u32>,
    token_quota: Option<u32>,
}

impl UsageTracker {
    /// Creates a new tracker with both token and request quotas for the given window size.
    ///
    /// # Arguments
    /// * `token_quota` - Maximum total tokens allowed within the window.
    /// * `request_quota` - Maximum number of requests allowed within the window.
    /// * `window_size_ms` - Length of the sliding window in milliseconds.
    pub fn new(token_quota: u32, request_quota: u32, window_size_ms: u64) -> Self {
        Self {
            token_quota: Some(token_quota),
            request_quota: Some(request_quota),
            window_size_ms,
            ..Self::default()
        }
    }


    /// Creates a tracker with both token and request quotas (default window 60 seconds).
    pub fn with_quota(token_quota: u32, request_quota: u32) -> Self {
        Self {
            token_quota: Some(token_quota),
            request_quota: Some(request_quota),
            ..Self::default()
        }
    }

    /// Creates a tracker with a custom window size (in milliseconds) and no quotas.
    pub fn with_window_size(window_size_ms: u64) -> Self {
        Self {
            window_size_ms,
            ..Self::default()
        }
    }

    /// Creates a tracker with only a token quota (default window 60 seconds).
    ///
    /// The quota applies to the total tokens accumulated within the window.
    pub fn with_token_quota(token_quota: u32) -> Self {
        Self {
            token_quota: Some(token_quota),
            ..Self::default()
        }
    }

    /// Creates a tracker with only a request quota (default window 60 seconds).
    ///
    /// The quota applies to the number of requests made within the window.
    pub fn with_request_quota(request_quota: u32) -> Self {
        Self {
            request_quota: Some(request_quota),
            ..Self::default()
        }
    }


    /// Records a new request with given token counts.
    ///
    /// Adds request with current timestamp and maintains queue size limit.
    fn add_request(&mut self, input_token: u32, output_token: u32) -> &mut Self {
        let timestamp = self.current_timestamp();
        self.request_infos.push_back(RequestInfo {
            input_token,
            output_token,
            timestamp,
        });

        // Prevent unbounded memory growth
        if self.request_infos.len() > MAX_BUFFER_SIZE {
            self.request_infos.pop_front();
        }

        self
    }

    /// Records a request by counting tokens from input/output strings.
    fn add_raw_request(&mut self, input_str: String, output_string: String) -> &mut Self {
        self.add_request(count_token(input_str), count_token(output_string))
    }

    /// Returns current system time in milliseconds since UNIX epoch.
    fn current_timestamp(&self) -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("Time went backwards")
            .as_millis() as u64
    }

    /// Returns timestamp marking the start of current window.
    fn window_start(&self) -> u64 {
        self.current_timestamp().saturating_sub(self.window_size_ms)
    }

    /// Removes all requests older than current window.
    ///
    /// Uses partition_point for efficient binary search on sorted timestamps.
    fn populate_expired(&mut self) -> &Self {
        self.request_infos.drain(..self.windows_start_index()).count();
        self
    }

    /// Returns references to all requests within current window.
    ///
    /// Maintains chronological order of requests.
    fn window_requests(&self) -> Vec<&RequestInfo> {
        self.request_infos.iter().skip(self.windows_start_index()).collect()
    }

    /// Returns index of first request within current window.
    ///
    /// Uses binary search (partition_point) since requests are time-ordered.
    fn windows_start_index(&self) -> usize {
        let window_start = self.window_start();

        self.request_infos
            .partition_point(|req| req.timestamp < window_start)
    }

    /// Returns the total number of requests made in the current window.
    ///
    /// This is the effective requests-per-window count.
    pub fn request_usage(&self) -> u32 {
        self.window_requests().len() as u32
    }


    /// Returns the total number of tokens consumed in the current window.
    ///
    /// This is the effective tokens-per-window count.
    pub fn token_usage(&self) -> u64 {
        self.window_requests()
            .iter()
            .map(|req| req.total_token() as u64)
            .sum()
    }

    /// Returns the current window size in milliseconds.
    pub fn window_size_ms(&self) -> u64 {
        self.window_size_ms
    }

    /// Returns the request quota for the window, if set.
    pub fn request_quota(&self) -> Option<u32> {
        self.request_quota
    }

    /// Returns the token quota for the window, if set.
    pub fn token_quota(&self) -> Option<u32> {
        self.token_quota
    }

    /// Returns remaining requests allowed in the current window, if quota exists.
    pub fn remaining_requests(&self) -> Option<u32> {
        self.request_quota.map(|quota| quota.saturating_sub(self.request_usage()))
    }

    /// Returns remaining tokens allowed in the current window, if quota exists.
    pub fn remaining_tokens(&self) -> Option<u64> {
        self.token_quota.map(|quota| (quota as u64).saturating_sub(self.token_usage()))
    }

    // Backward compatibility aliases
    pub fn remaining_rpm(&self) -> Option<u32> {
        self.remaining_requests()
    }

    pub fn remaining_tpm(&self) -> Option<u64> {
        self.remaining_tokens()
    }

    /// Checks if a request with given input tokens can be made now.
    ///
    /// Verifies both request and token quotas would not be exceeded.
    fn can_make_request(&self, input_tokens: u32) -> bool {
        self.can_make_request_quota() && self.can_make_token_quota(input_tokens)
    }

    /// Checks if request quota allows another request now.
    fn can_make_request_quota(&self) -> bool {
        self.request_quota.is_none_or(|quota| self.request_usage() < quota)
    }

    /// Checks if token quota allows another request with given tokens.
    ///
    /// Assumes output tokens are unknown, only checks input tokens.
    fn can_make_token_quota(&self, input_tokens: u32) -> bool {
        self.token_quota
            .is_none_or(|quota| (self.token_usage() as u32).saturating_add(input_tokens) <= quota)
    }


    /// Checks if request with given input text can be made now.
    fn can_make_raw_request(&self, input_string: String) -> bool {
        self.can_make_request(count_token(input_string))
    }

    // ====== Waiting Time Calculation ======

    /// Estimates time until all current window requests expire.
    ///
    /// Returns time until the earliest request in window expires.
    fn estimated_full_cool_down_time(&self) -> u64 {
        let window_reqs = self.window_requests();
        if window_reqs.is_empty() {
            return 0;
        }
        let earliest_exit_time = window_reqs[0].timestamp + self.window_size_ms;
        earliest_exit_time.saturating_sub(self.current_timestamp())
    }

    /// Estimates wait time based on token quota for given input tokens.
    fn estimated_waiting_time_for_tokens(&self, input_tokens: u32) -> u64 {
        self.estimated_waiting_time_for_request(input_tokens, 0)
    }

    /// Estimates wait time based on token quota for given input text.
    fn estimated_waiting_time_for_text(&self, input_text: String) -> u64 {
        self.estimated_waiting_time_for_tokens(count_token(input_text))
    }

    /// Estimates total wait time considering both request and token quotas.
    ///
    /// Returns maximum of request and token wait times.
    fn estimated_waiting_time_for_request(&self, input_tokens: u32, output_tokens: u32) -> u64 {
        let req_wait = self.calculate_request_wait();
        let token_wait = self.calculate_token_wait_for_tokens(input_tokens + output_tokens);
        req_wait.max(token_wait)
    }

    /// Calculates time until request quota allows another request.
    ///
    /// Finds the request that must expire to free up a slot.
    fn calculate_request_wait(&self) -> u64 {
        self.request_quota.map_or(0, |quota| {
            let window_reqs = self.window_requests();
            let current_count = window_reqs.len() as u32;

            if current_count < quota {
                return 0;
            }

            let requests_to_remove = (current_count + 1 - quota) as usize;
            if let Some(req) = window_reqs.get(requests_to_remove - 1) {
                let exit_time = req.timestamp + self.window_size_ms;
                exit_time.saturating_sub(self.current_timestamp())
            } else {
                0
            }
        })
    }

    /// Calculates time until token quota allows given number of new tokens.
    ///
    /// Finds which request must expire to free up enough tokens.
    fn calculate_token_wait_for_tokens(&self, new_tokens: u32) -> u64 {
        self.token_quota.map_or(0, |quota| {
            let window_reqs = self.window_requests();
            let current_tokens: u64 = window_reqs
                .iter()
                .map(|req| req.total_token() as u64)
                .sum();

            if current_tokens + new_tokens as u64 <= quota as u64 {
                return 0;
            }

            let excess_tokens = (current_tokens + new_tokens as u64) - quota as u64;
            self.find_exit_time_for_excess_tokens(&window_reqs, excess_tokens)
        })
    }


    /// Finds the earliest time when enough tokens expire to satisfy quota.
    ///
    /// Accumulates tokens from oldest to newest until reaching excess_tokens.
    fn find_exit_time_for_excess_tokens(&self, requests: &[&RequestInfo], excess_tokens: u64) -> u64 {
        let mut accumulated: u64 = 0;
        for req in requests {
            accumulated += req.total_token() as u64;
            if accumulated >= excess_tokens {
                let exit_time = req.timestamp + self.window_size_ms;
                return exit_time.saturating_sub(self.current_timestamp());
            }
        }
        0
    }

    /// Checks if request can be sent immediately (zero wait time).
    fn can_send_now(&self, input_tokens: u32, output_tokens: u32) -> bool {
        self.estimated_waiting_time_for_request(input_tokens, output_tokens) == 0
    }

    /// Checks if request with given text can be sent immediately.
    fn can_send_text_now(&self, input_text: String) -> bool {
        self.estimated_waiting_time_for_text(input_text) == 0
    }

    /// Builds cumulative token usage over time for debugging.
    ///
    /// Returns vector of (timestamp, cumulative_tokens).
    fn build_cumulative_tokens(&self, requests: &[&RequestInfo]) -> Vec<(u64, u64)> {
        let mut result = Vec::with_capacity(requests.len());
        let mut total: u64 = 0;
        for req in requests {
            total += req.total_token() as u64;
            result.push((req.timestamp, total));
        }
        result
    }

    /// Alias for estimated_full_cool_down_time.
    fn estimated_waiting_time(&self) -> u64 {
        self.estimated_full_cool_down_time()
    }
}

impl Default for UsageTracker {
    /// Creates tracker with default settings:
    /// - 60,000 millisecond window
    /// - No quotas
    /// - Pre-allocated queue with MIN_BUFFER_SIZE capacity
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
    use std::thread;
    use std::time::Duration;

    fn create_request_info(input_token: u32, output_token: u32, timestamp: u64) -> RequestInfo {
        RequestInfo {
            input_token,
            output_token,
            timestamp,
        }
    }

    fn populate_queue(tracker: &mut UsageTracker, requests: Vec<RequestInfo>) {
        tracker.request_infos.clear();
        for req in requests {
            tracker.request_infos.push_back(req);
        }
    }

    #[test]
    fn test_default_initialization() {
        let tracker = UsageTracker::default();
        assert_eq!(tracker.window_size_ms, 60_000);
        assert_eq!(tracker.request_infos.len(), 0);
        assert_eq!(tracker.request_quota, None);
        assert_eq!(tracker.token_quota, None);
    }

    #[test]
    fn test_new_with_quotas() {
        let tracker = UsageTracker::new(1000, 60, 60_000);
        assert_eq!(tracker.token_quota, Some(1000));
        assert_eq!(tracker.request_quota, Some(60));
        assert_eq!(tracker.window_size_ms, 60_000);
    }

    #[test]
    fn test_with_quota_constructor() {
        let tracker = UsageTracker::with_quota(1000, 60);
        assert_eq!(tracker.token_quota, Some(1000));
        assert_eq!(tracker.request_quota, Some(60));
        assert_eq!(tracker.window_size_ms, 60_000);
    }

    #[test]
    fn test_with_token_quota_constructor() {
        let tracker = UsageTracker::with_token_quota(1000);
        assert_eq!(tracker.token_quota, Some(1000));
        assert_eq!(tracker.request_quota, None);
        assert_eq!(tracker.window_size_ms, 60_000);
    }

    #[test]
    fn test_with_request_quota_constructor() {
        let tracker = UsageTracker::with_request_quota(60);
        assert_eq!(tracker.token_quota, None);
        assert_eq!(tracker.request_quota, Some(60));
        assert_eq!(tracker.window_size_ms, 60_000);
    }

    #[test]
    fn test_with_window_size_constructor() {
        let tracker = UsageTracker::with_window_size(30_000);
        assert_eq!(tracker.token_quota, None);
        assert_eq!(tracker.request_quota, None);
        assert_eq!(tracker.window_size_ms, 30_000);
    }

    #[test]
    fn test_add_request() {
        let mut tracker = UsageTracker::default();
        let timestamp_before = tracker.current_timestamp();

        tracker.add_request(100, 50);

        assert_eq!(tracker.request_infos.len(), 1);
        let request = &tracker.request_infos[0];
        assert_eq!(request.input_token, 100);
        assert_eq!(request.output_token, 50);
        assert!(request.timestamp >= timestamp_before);
        assert!(request.timestamp <= timestamp_before + 100);
    }

    #[test]
    fn test_populate_expired() {
        let mut tracker = UsageTracker::with_window_size(1000);
        let now = tracker.current_timestamp();

        let requests = vec![
            create_request_info(10, 5, now - 2000),
            create_request_info(10, 5, now - 1500),
            create_request_info(10, 5, now - 500),
            create_request_info(10, 5, now - 200),
        ];
        populate_queue(&mut tracker, requests);

        tracker.populate_expired();

        assert_eq!(tracker.request_infos.len(), 2);
        assert_eq!(tracker.request_infos[0].timestamp, now - 500);
        assert_eq!(tracker.request_infos[1].timestamp, now - 200);
    }

    #[test]
    fn test_window_requests() {
        let mut tracker = UsageTracker::with_window_size(1000);
        let now = tracker.current_timestamp();

        let requests = vec![
            create_request_info(10, 5, now - 2000),
            create_request_info(10, 5, now - 1500),
            create_request_info(10, 5, now - 500),
            create_request_info(10, 5, now - 200),
        ];
        populate_queue(&mut tracker, requests);

        let window_reqs = tracker.window_requests();
        assert_eq!(window_reqs.len(), 2);
        assert_eq!(window_reqs[0].timestamp, now - 500);
        assert_eq!(window_reqs[1].timestamp, now - 200);
    }

    #[test]
    fn test_rpm_and_tpm() {
        let mut tracker = UsageTracker::with_window_size(1000);
        let now = tracker.current_timestamp();

        let requests = vec![
            create_request_info(100, 50, now - 500),
            create_request_info(200, 30, now - 400),
            create_request_info(150, 70, now - 300),
        ];
        populate_queue(&mut tracker, requests);

        assert_eq!(tracker.request_usage(), 3);
        assert_eq!(tracker.token_usage(), 600);
    }

    #[test]
    fn test_calculate_request_wait() {
        let tracker = UsageTracker::with_quota(1000, 2);
        let mut tracker_with_requests = UsageTracker::with_window_size(1000);

        let now = tracker_with_requests.current_timestamp();
        let requests = vec![
            create_request_info(10, 5, now - 900),
            create_request_info(10, 5, now - 500),
        ];
        populate_queue(&mut tracker_with_requests, requests);

        let mut tracker = UsageTracker::with_quota(1000, 2);
        tracker.request_infos = tracker_with_requests.request_infos;
        tracker.window_size_ms = tracker_with_requests.window_size_ms;

        let wait_time = tracker.calculate_request_wait();
        assert!((50..=150).contains(&wait_time));
    }

    #[test]
    fn test_calculate_token_wait() {
        let tracker = UsageTracker::with_quota(300, 10);
        let mut tracker_with_requests = UsageTracker::with_window_size(1000);

        let now = tracker_with_requests.current_timestamp();
        let requests = vec![
            create_request_info(100, 50, now - 900),
            create_request_info(100, 50, now - 500),
        ];
        populate_queue(&mut tracker_with_requests, requests);

        let mut tracker = UsageTracker::with_quota(300, 10);
        tracker.request_infos = tracker_with_requests.request_infos;
        tracker.window_size_ms = tracker_with_requests.window_size_ms;

        let wait_time = tracker.calculate_token_wait_for_tokens(50);
        assert!((50..=150).contains(&wait_time));
    }

    #[test]
    fn test_real_time_expiration() {
        let mut tracker = UsageTracker::with_window_size(100);
        tracker.add_request(10, 5);
        assert_eq!(tracker.window_requests().len(), 1);

        thread::sleep(Duration::from_millis(150));

        tracker.populate_expired();
        assert_eq!(tracker.window_requests().len(), 0);
        assert_eq!(tracker.request_infos.len(), 0);
    }

    #[test]
    fn test_queue_growth_limit() {
        let mut tracker = UsageTracker::default();

        for i in 0..MAX_BUFFER_SIZE + 10 {
            tracker.add_request(i as u32, i as u32);
        }

        assert_eq!(tracker.request_infos.len(), MAX_BUFFER_SIZE);
        assert_eq!(tracker.request_infos[0].input_token, 10);
    }

    #[test]
    fn test_edge_cases() {
        let tracker = UsageTracker::with_request_quota(0);
        assert!(!tracker.can_make_request_quota());

        let tracker = UsageTracker::with_token_quota(0);
        assert!(!tracker.can_make_token_quota(1));

        let tracker = UsageTracker::default();
        assert!(tracker.can_make_request(u32::MAX));

        let mut tracker = UsageTracker::default();
        tracker.add_request(0, 0);
        assert_eq!(tracker.token_usage(), 0);

        let wait_time = tracker.estimated_full_cool_down_time();
        assert!(wait_time <= tracker.window_size_ms);
        assert!(wait_time > 0);
    }

    #[test]
    fn test_find_exit_time_for_excess_tokens() {
        let tracker = UsageTracker::with_window_size(1000);
        let now = tracker.current_timestamp();

        let requests = vec![
            create_request_info(100, 50, now - 900),
            create_request_info(30, 20, now - 600),
            create_request_info(10, 5, now - 300),
        ];

        let req_refs: Vec<&RequestInfo> = requests.iter().collect();

        let exit_time1 = tracker.find_exit_time_for_excess_tokens(&req_refs, 100);
        assert_eq!(exit_time1, 100);

        let exit_time2 = tracker.find_exit_time_for_excess_tokens(&req_refs, 180);
        assert_eq!(exit_time2, 400);
    }

    #[test]
    fn test_can_make_request_checks() {
        let mut tracker = UsageTracker::with_quota(1000, 2);
        let now = tracker.current_timestamp();

        tracker.add_request(100, 50);
        assert!(tracker.can_make_request_quota());
        assert!(tracker.can_make_token_quota(100));

        tracker.add_request(200, 100);
        assert!(!tracker.can_make_request_quota());
        assert!(tracker.can_make_token_quota(50));
        assert!(!tracker.can_make_token_quota(600));
    }

    #[test]
    fn test_remaining_quotas() {
        let mut tracker = UsageTracker::with_quota(1000, 3);
        let now = tracker.current_timestamp();

        tracker.add_request(100, 50);

        assert_eq!(tracker.remaining_requests(), Some(2));
        assert_eq!(tracker.remaining_tokens(), Some(850));

        tracker.add_request(200, 100);

        assert_eq!(tracker.remaining_requests(), Some(1));
        assert_eq!(tracker.remaining_tokens(), Some(550));
    }

    #[test]
    fn test_build_cumulative_tokens() {
        let tracker = UsageTracker::with_window_size(1000);
        let now = tracker.current_timestamp();

        let requests = vec![
            create_request_info(100, 50, now - 900),
            create_request_info(30, 20, now - 600),
            create_request_info(10, 5, now - 300)
        ];

        let cumulative = tracker.build_cumulative_tokens(&requests.iter().collect::<Vec<_>>());

        assert_eq!(cumulative.len(), 3);
        assert_eq!(cumulative[0], (now - 900, 150));
        assert_eq!(cumulative[1], (now - 600, 200));
        assert_eq!(cumulative[2], (now - 300, 215));
    }
}