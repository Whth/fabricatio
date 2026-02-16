use crate::constants::{MAX_BUFFER_SIZE, MIN_BUFFER_SIZE};
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

/// Tracks API usage within a sliding time window for quota management
///
/// Maintains a queue of past requests and provides methods to check
/// current usage against RPM (requests per minute) and TPM (tokens per minute) quotas.
#[derive(Debug)]
pub struct UsageTracker {
    request_infos: VecDeque<RequestInfo>,
    window_size_ms: u64,
    rpm_quota: Option<u32>,
    tpm_quota: Option<u32>,
}

impl UsageTracker {
    /// Creates a new tracker with both RPM and TPM quotas
    ///
    /// Window size defaults to 60 seconds (60000ms)
    pub fn new(tpm: u32, rpm: u32) -> Self {
        Self {
            tpm_quota: Some(tpm),
            rpm_quota: Some(rpm),
            ..Self::default()
        }
    }

    /// Creates a tracker with custom window size (in milliseconds)
    pub fn with_window_size(window_size_ms: u64) -> Self {
        Self {
            window_size_ms,
            ..Self::default()
        }
    }

    /// Creates a tracker with only TPM quota
    pub fn with_tpm(tpm_quota: u32) -> Self {
        Self {
            tpm_quota: Some(tpm_quota),
            ..Self::default()
        }
    }

    /// Creates a tracker with only RPM quota
    pub fn with_rpm(rpm_quota: u32) -> Self {
        Self {
            rpm_quota: Some(rpm_quota),
            ..Self::default()
        }
    }

    /// Records a new request with given token counts
    ///
    /// Adds request with current timestamp and maintains queue size limit
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

    /// Records a request by counting tokens from input/output strings
    fn add_raw_request(&mut self, input_str: String, output_string: String) -> &mut Self {
        self.add_request(count_token(input_str), count_token(output_string))
    }

    /// Returns current system time in milliseconds since UNIX epoch
    fn current_timestamp(&self) -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("Time went backwards")
            .as_millis() as u64
    }

    /// Returns timestamp marking the start of current window
    fn window_start(&self) -> u64 {
        self.current_timestamp().saturating_sub(self.window_size_ms)
    }

    /// Removes all requests older than current window
    ///
    /// Uses partition_point for efficient binary search on sorted timestamps
    fn populate_expired(&mut self) -> &Self {
        self.request_infos.drain(..self.windows_start_index()).count();
        self
    }

    /// Returns references to all requests within current window
    ///
    /// Maintains chronological order of requests
    fn window_requests(&self) -> Vec<&RequestInfo> {
        self.request_infos.iter().skip(self.windows_start_index()).collect()
    }

    /// Returns index of first request within current window
    ///
    /// Uses binary search (partition_point) since requests are time-ordered
    fn windows_start_index(&self) -> usize {
        let window_start = self.window_start();

        self.request_infos
            .partition_point(|req| req.timestamp < window_start)
    }

    /// Calculates current RPM (requests per minute) within window
    fn rpm(&self) -> u32 {
        self.window_requests().len() as u32
    }

    /// Calculates current TPM (tokens per minute) within window
    ///
    /// Returns u64 to prevent overflow when summing many requests
    fn tpm(&self) -> u64 {
        self.window_requests()
            .iter()
            .map(|req| req.total_token() as u64)
            .sum()
    }

    /// Returns current window size in milliseconds
    fn window_size_ms(&self) -> u64 {
        self.window_size_ms
    }

    /// Sets new window size in milliseconds
    fn set_window_size(&mut self, window_size_ms: u64) {
        self.window_size_ms = window_size_ms;
    }

    // ====== Quota Management ======

    /// Sets or removes RPM quota
    fn set_rpm_quota(&mut self, quota: Option<u32>) {
        self.rpm_quota = quota;
    }

    /// Sets or removes TPM quota
    fn set_tpm_quota(&mut self, quota: Option<u32>) {
        self.tpm_quota = quota;
    }

    /// Returns current RPM quota if set
    fn rpm_quota(&self) -> Option<u32> {
        self.rpm_quota
    }

    /// Returns current TPM quota if set
    fn tpm_quota(&self) -> Option<u32> {
        self.tpm_quota
    }

    /// Returns remaining requests allowed in current window, if quota exists
    fn remaining_rpm(&self) -> Option<u32> {
        self.rpm_quota.map(|quota| quota.saturating_sub(self.rpm()))
    }

    /// Returns remaining tokens allowed in current window, if quota exists
    fn remaining_tpm(&self) -> Option<u64> {
        self.tpm_quota.map(|quota| (quota as u64).saturating_sub(self.tpm()))
    }

    /// Checks if a request with given input tokens can be made now
    ///
    /// Verifies both RPM and TPM quotas would not be exceeded
    fn can_make_request(&self, input_tokens: u32) -> bool {
        self.can_make_rpm_request() && self.can_make_tpm_request(input_tokens)
    }

    /// Checks if RPM quota allows another request now
    fn can_make_rpm_request(&self) -> bool {
        self.rpm_quota.is_none_or(|quota| self.rpm() < quota)
    }

    /// Checks if TPM quota allows another request with given tokens
    ///
    /// Assumes output tokens are unknown, only checks input tokens
    fn can_make_tpm_request(&self, input_tokens: u32) -> bool {
        self.tpm_quota
            .is_none_or(|quota| (self.tpm() as u32).saturating_add(input_tokens) <= quota)
    }

    /// Checks if request with given input text can be made now
    fn can_make_raw_request(&self, input_string: String) -> bool {
        self.can_make_request(count_token(input_string))
    }

    // ====== Waiting Time Calculation ======

    /// Estimates time until all current window requests expire
    ///
    /// Returns time until the earliest request in window expires
    fn estimated_full_cool_down_time(&self) -> u64 {
        let window_reqs = self.window_requests();
        if window_reqs.is_empty() {
            return 0;
        }
        let earliest_exit_time = window_reqs[0].timestamp + self.window_size_ms;
        earliest_exit_time.saturating_sub(self.current_timestamp())
    }

    /// Estimates wait time based on token quota for given input tokens
    fn estimated_waiting_time_for_tokens(&self, input_tokens: u32) -> u64 {
        self.estimated_waiting_time_for_request(input_tokens, 0)
    }

    /// Estimates wait time based on token quota for given input text
    fn estimated_waiting_time_for_text(&self, input_text: String) -> u64 {
        self.estimated_waiting_time_for_tokens(count_token(input_text))
    }

    /// Estimates total wait time considering both RPM and TPM quotas
    ///
    /// Returns maximum of RPM and TPM wait times
    fn estimated_waiting_time_for_request(&self, input_tokens: u32, output_tokens: u32) -> u64 {
        let rpm_wait = self.calculate_rpm_wait();
        let tpm_wait = self.calculate_tpm_wait_for_tokens(input_tokens + output_tokens);
        rpm_wait.max(tpm_wait)
    }

    /// Calculates time until RPM quota allows another request
    ///
    /// Finds the request that must expire to free up a slot
    fn calculate_rpm_wait(&self) -> u64 {
        self.rpm_quota.map_or(0, |quota| {
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

    /// Calculates time until TPM quota allows given number of new tokens
    ///
    /// Finds which request must expire to free up enough tokens
    fn calculate_tpm_wait_for_tokens(&self, new_tokens: u32) -> u64 {
        self.tpm_quota.map_or(0, |quota| {
            let window_reqs = self.window_requests();
            let current_tpm: u64 = window_reqs
                .iter()
                .map(|req| req.total_token() as u64)
                .sum();

            if current_tpm + new_tokens as u64 <= quota as u64 {
                return 0;
            }

            let excess_tokens = (current_tpm + new_tokens as u64) - quota as u64;
            self.find_exit_time_for_excess_tokens(&window_reqs, excess_tokens)
        })
    }

    /// Finds the earliest time when enough tokens expire to satisfy quota
    ///
    /// Accumulates tokens from oldest to newest until reaching excess_tokens
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

    /// Checks if request can be sent immediately (zero wait time)
    fn can_send_now(&self, input_tokens: u32, output_tokens: u32) -> bool {
        self.estimated_waiting_time_for_request(input_tokens, output_tokens) == 0
    }

    /// Checks if request with given text can be sent immediately
    fn can_send_text_now(&self, input_text: String) -> bool {
        self.estimated_waiting_time_for_text(input_text) == 0
    }

    /// Builds cumulative token usage over time for debugging
    ///
    /// Returns vector of (timestamp, cumulative_tokens)
    fn build_cumulative_tokens(&self, requests: &[&RequestInfo]) -> Vec<(u64, u64)> {
        let mut result = Vec::with_capacity(requests.len());
        let mut total: u64 = 0;
        for req in requests {
            total += req.total_token() as u64;
            result.push((req.timestamp, total));
        }
        result
    }

    /// Alias for estimated_full_cool_down_time
    fn estimated_waiting_time(&self) -> u64 {
        self.estimated_full_cool_down_time()
    }
}

impl Default for UsageTracker {
    /// Creates tracker with default settings:
    /// - 60 second window
    /// - No quotas
    /// - Pre-allocated queue with MIN_BUFFER_SIZE capacity
    fn default() -> Self {
        Self {
            request_infos: VecDeque::with_capacity(MIN_BUFFER_SIZE),
            window_size_ms: 60_000,
            rpm_quota: None,
            tpm_quota: None,
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
        assert_eq!(tracker.rpm_quota, None);
        assert_eq!(tracker.tpm_quota, None);
    }

    #[test]
    fn test_new_with_quotas() {
        let tracker = UsageTracker::new(1000, 60);
        assert_eq!(tracker.tpm_quota, Some(1000));
        assert_eq!(tracker.rpm_quota, Some(60));
        assert_eq!(tracker.window_size_ms, 60_000);
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

        assert_eq!(tracker.rpm(), 3);
        assert_eq!(tracker.tpm(), 600);
    }

    #[test]
    fn test_calculate_rpm_wait() {
        let mut tracker = UsageTracker::with_window_size(1000);
        tracker.set_rpm_quota(Some(2));

        let now = tracker.current_timestamp();
        let requests = vec![
            create_request_info(10, 5, now - 900),
            create_request_info(10, 5, now - 500),
        ];
        populate_queue(&mut tracker, requests);

        let wait_time = tracker.calculate_rpm_wait();
        assert!((50..=150).contains(&wait_time));
    }

    #[test]
    fn test_real_time_expiration() {
        let mut tracker = UsageTracker::with_window_size(100);
        tracker.add_request(10, 5);
        assert_eq!(tracker.window_requests().len(), 1);

        thread::sleep(Duration::from_millis(150));

        assert_eq!(tracker.window_requests().len(), 0);

        tracker.populate_expired();
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
        let mut tracker = UsageTracker::default();

        tracker.set_rpm_quota(Some(0));
        assert!(!tracker.can_make_rpm_request());

        tracker.set_tpm_quota(Some(0));
        assert!(!tracker.can_make_tpm_request(1));

        tracker.set_rpm_quota(None);
        tracker.set_tpm_quota(None);
        assert!(tracker.can_make_request(u32::MAX));

        tracker.add_request(0, 0);
        assert_eq!(tracker.tpm(), 0);

        let wait_time = tracker.estimated_full_cool_down_time();
        assert_eq!(wait_time, tracker.window_size_ms);
    }

    #[test]
    fn test_find_exit_time_for_excess_tokens() {
        let tracker = UsageTracker::with_window_size(1000);
        let now = tracker.current_timestamp();

        let requests = [
            create_request_info(100, 50, now - 900),
            create_request_info(30, 20, now - 600),
            create_request_info(10, 5, now - 300)];

        let req_refs: Vec<&RequestInfo> = requests.iter().collect();

        let exit_time1 = tracker.find_exit_time_for_excess_tokens(&req_refs, 100);
        assert_eq!(exit_time1, 100);

        let exit_time2 = tracker.find_exit_time_for_excess_tokens(&req_refs, 180);
        assert_eq!(exit_time2, 400);
    }
}