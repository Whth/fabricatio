//! A fake System One server, so the client can be exercised through a real HTTP stack.

use std::sync::Arc;
use std::time::Duration;

use parking_lot::Mutex;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};

use jevlin::{
    Answers, ChoiceAnswer, Deserialize, NoulAnswer, Question, Request, RetryConfig, ScoreAnswer,
    SystemOne,
};

/// The state every test evaluates.
pub const STATE: &str = "Help! My payouts have been failing for 3 days.";

/// A request with one yes/no question.
pub fn request() -> Request {
    Request::new(STATE).with_question("is_urgent", Question::noul("Does this convey urgency?"))
}

/// A question set declared where its answers are read.
#[derive(Answers, Deserialize)]
pub struct Triage {
    #[jev(noul, "Does this convey urgency?")]
    pub is_urgent: NoulAnswer,
    #[jev(
        choice,
        "Which team should handle this?",
        billing = "Payments, invoicing, refunds",
        technical = "Bugs, outages, integrations"
    )]
    pub department: ChoiceAnswer,
    #[jev(
        score,
        "How frustrated is the customer?",
        "Calm",
        "Frustrated",
        "Very angry"
    )]
    pub frustration: ScoreAnswer,
}

/// The documented response shape, with its single answer filed under `id`.
pub fn answered(id: &str) -> String {
    format!(
        r#"{{"model":"jev-1.13.0","answers":{{"{id}":{{"type":"noul","noul":0.95}}}},"usage":{{"input_tokens":296,"output_tokens":20}}}}"#
    )
}

/// The documented response to the three questions of [`Triage`].
pub fn triage() -> String {
    r#"{"model":"jev-1.13.0","answers":{
        "is_urgent":{"type":"noul","noul":0.95},
        "department":{"type":"choice","choice":"billing","probabilities":{"billing":0.88,"technical":0.12},"confidence":0.81},
        "frustration":{"type":"score","score":1.05,"legend":{"0":"Calm","1":"Frustrated","2":"Very angry"},"probabilities":{"0":0.0,"1":0.95,"2":0.05},"confidence":0.92}},
        "usage":{"input_tokens":296,"output_tokens":20}}"#
        .to_string()
}

/// One canned HTTP reply.
pub struct Reply {
    status: u16,
    body: String,
    retry_after: Option<String>,
    hang: bool,
}

impl Reply {
    pub fn ok(body: &str) -> Self {
        Self::new(200, body)
    }

    pub fn error(status: u16) -> Self {
        Self::new(
            status,
            r#"{"errors":[{"detail":"`questions` is required"}]}"#,
        )
    }

    /// Accepts the request and never answers it.
    pub fn hang() -> Self {
        let mut reply = Self::new(200, "");
        reply.hang = true;
        reply
    }

    /// Asks for a delay in whole seconds, the shape the API sends.
    pub fn with_retry_after(mut self, seconds: u64) -> Self {
        self.retry_after = Some(seconds.to_string());
        self
    }

    /// Asks for a delay in a shape the client does not read, such as an HTTP date.
    pub fn with_raw_retry_after(mut self, value: &str) -> Self {
        self.retry_after = Some(value.to_string());
        self
    }

    fn new(status: u16, body: &str) -> Self {
        Self {
            status,
            body: body.to_string(),
            retry_after: None,
            hang: false,
        }
    }
}

/// A local HTTP server that serves `replies` in order and records every request it received.
pub struct FakeApi {
    pub base_url: String,
    received: Arc<Mutex<Vec<String>>>,
}

impl FakeApi {
    pub async fn start(replies: Vec<Reply>) -> Self {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let base_url = format!("http://{}", listener.local_addr().unwrap());
        let received = Arc::new(Mutex::new(Vec::new()));
        let recorded = Arc::clone(&received);
        tokio::spawn(async move {
            for reply in replies {
                let Ok((mut stream, _)) = listener.accept().await else {
                    return;
                };
                let Some(request) = read_request(&mut stream).await else {
                    return;
                };
                recorded.lock().push(request);
                if reply.hang {
                    tokio::time::sleep(Duration::from_secs(30)).await;
                    continue;
                }
                let _ = respond(&mut stream, &reply).await;
            }
        });
        Self { base_url, received }
    }

    /// A client pointed at this server, with the default retry policy.
    pub fn client(&self) -> SystemOne {
        self.client_with(RetryConfig::default())
    }

    /// A client pointed at this server, with `retry` in place of the default policy.
    pub fn client_with(&self, retry: RetryConfig) -> SystemOne {
        SystemOne::builder("test-key")
            .base_url(self.base_url.clone())
            .retry(retry)
            .build()
            .unwrap()
    }

    /// Every request the server received, verbatim.
    pub fn requests(&self) -> Vec<String> {
        self.received.lock().clone()
    }
}

/// Reads one whole HTTP request — head and body — off the socket.
async fn read_request(stream: &mut TcpStream) -> Option<String> {
    let mut buffer = Vec::new();
    let mut chunk = [0_u8; 1024];
    loop {
        let read = stream.read(&mut chunk).await.ok()?;
        if read == 0 {
            return Some(String::from_utf8_lossy(&buffer).into_owned());
        }
        buffer.extend_from_slice(&chunk[..read]);
        let Some(head_end) = head_end(&buffer) else {
            continue;
        };
        let head = String::from_utf8_lossy(&buffer[..head_end]);
        let length = header_value(&head, "content-length")
            .and_then(|length| length.parse::<usize>().ok())
            .unwrap_or(0);
        if buffer.len() >= head_end + length {
            return Some(String::from_utf8_lossy(&buffer).into_owned());
        }
    }
}

async fn respond(stream: &mut TcpStream, reply: &Reply) -> std::io::Result<()> {
    let mut head = format!(
        "HTTP/1.1 {} {}\r\ncontent-type: application/json\r\ncontent-length: {}\r\nconnection: close\r\n",
        reply.status,
        reason(reply.status),
        reply.body.len()
    );
    if let Some(value) = &reply.retry_after {
        head.push_str(&format!("retry-after: {value}\r\n"));
    }
    head.push_str("\r\n");
    stream.write_all(head.as_bytes()).await?;
    stream.write_all(reply.body.as_bytes()).await?;
    stream.shutdown().await
}

fn reason(status: u16) -> &'static str {
    match status {
        200 => "OK",
        401 => "Unauthorized",
        422 => "Unprocessable Entity",
        429 => "Too Many Requests",
        500 => "Internal Server Error",
        529 => "Overloaded",
        _ => "Error",
    }
}

fn head_end(buffer: &[u8]) -> Option<usize> {
    buffer
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .map(|index| index + 4)
}

/// The value of header `name` in an HTTP head, matched without case.
pub fn header_value<'a>(head: &'a str, name: &str) -> Option<&'a str> {
    head.lines().find_map(|line| {
        let (key, value) = line.split_once(':')?;
        key.eq_ignore_ascii_case(name).then(|| value.trim())
    })
}

/// The head and the parsed JSON body of a recorded request.
pub fn parts(request: &str) -> (&str, serde_json::Value) {
    let (head, body) = request.split_once("\r\n\r\n").unwrap();
    (head, serde_json::from_str(body).unwrap())
}
