# TODO

- [x] Replace litellm with native rust impl
    - [x] Port deprecated mock utils to thryd impl
    - [x] Port tests to new mock utils
    - [x] Sync documentations
    - [x] Router cache support ttl and eviction
- [x] Use `Thryd` impl to move some requests to rust side
    - [x] All core LLM operations already routed through `rust.router_usage`
- [x] `thryd::Router` use concurrent safe impl
- [x] `Thryd` router support retry
