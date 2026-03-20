# Thryd

A lightweight, embedded LLM request router with caching.

## Features

- **Multi-provider routing** - Route requests across multiple LLM providers
- **Token tracking** - Track token usage with sliding window rate limiting
- **Persistent caching** - Cache responses using sled (embedded database)
- **Multiple strategies** - Round-robin, least-loaded, first-available

## Usage

### Basic Example

```rust
use thryd::{Router, RoutingStrategy, RouteContext, Deployment};
use thryd::provider::LlmProvider;
use secrecy::SecretString;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create a provider
    let deployment = Deployment::new("openai-gpt4", "openai", "gpt-4");
    let provider = LlmProvider::new(
        deployment,
        SecretString::new("your-api-key".to_string())
    )?;

    // Build router
    let router = Router::new(RoutingStrategy::LeastLoaded)
        .add_provider(provider, 100);

    // Route a request
    let context = RouteContext::new()
        .with_model("gpt-4");

    let response = router.route_and_execute(&context, "Hello world!").await?;
    println!("Response: {}", response);

    Ok(())
}
```

### With Configuration

```rust
use thryd::{ThrydConfig, RoutingStrategy, CacheConfig};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let config = ThrydConfig {
        strategy: RoutingStrategy::LeastLoaded,
        cache: Some(CacheConfig {
            max_capacity: 1000,
            time_to_live: std::time::Duration::from_secs(3600),
            persist_path: Some("thryd_cache".into()),
        }),
        providers: vec![
            thryd::ProviderConfig {
                name: "openai-gpt4".into(),
                provider_type: "openai".into(),
                model: "gpt-4".into(),
                api_base: None,
                api_key: Some(std::env::var("OPENAI_API_KEY").unwrap()),
                priority: 100,
            },
            thryd::ProviderConfig {
                name: "anthropic".into(),
                provider_type: "anthropic".into(),
                model: "claude-3".into(),
                api_base: Some("https://api.anthropic.com/v1".into()),
                api_key: Some(std::env::var("ANTHROPIC_API_KEY").unwrap()),
                priority: 50,
            },
        ],
    };

    let mut router = thryd::init(config).await?;

    let context = thryd::RouteContext::new()
        .with_model("gpt-4");

    let response = router.route_and_execute(&context, "Hello!").await?;
    println!("Response: {}", response);

    Ok(())
}
```

### Rate Limiting

The tracker tracks requests and tokens within a sliding window:

```rust
use thryd::tracker::UsageTracker;


fn main() {

    // Create tracker with 60 requests/min and 90000 tokens/min
    let tracker = UsageTracker::new(90000, 60, 60_000);

    // Record a request (100 input tokens, 50 output tokens)
    tracker.add_request(100, 50);

    // Check if we can make another request
    if tracker.can_make_request(100) {
        // Make request
    }

    // Get current usage
    let requests_used = tracker.request_usage();
    let tokens_used = tracker.token_usage();
    let remaining = tracker.remaining_requests();
}
```

### Routing Strategies

- **RoundRobin** - Cycles through providers in order
- **LeastLoaded** - Selects provider with lowest current usage
- **FirstAvailable** - Uses first provider that can handle the request

## Architecture

```
thryd/
├── tracker.rs    - Token usage tracking and rate limiting
├── provider.rs   - LLM provider abstraction
├── cache.rs     - Persistent caching (sled)
├── route.rs     - Request routing logic
└── lib.rs       - Main entry point
```

## License

MIT
