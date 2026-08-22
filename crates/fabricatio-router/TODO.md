# TODO

- [x] Extract `Router` from `fabricatio-core` into standalone `fabricatio-router` crate
- [x] Replace `UseLLM` with native rust impl
    - [x] Fix the mock utils that is break by the replacement.
    - [x] router support `no_cache`
- [x] Embedding fail without any debug info fix
- [x] sparse cache for embedding
- [ ] Add multimodal LLM support (`aaskv` — text + image input).
    - [ ] `ContentPart` enum (`Text` / `ImageUrl`) + `content: Vec<ContentPart>` field on `CompletionRequest` — backward
      compatible (empty `content` falls back to `message` string)
    - [ ] OpenAI serialization: switch `.content(message)` to `.content(content_parts)` using `async-openai`'s existing
      `ChatCompletionRequestMessageContentPart` types
    - [ ] Cache key update: `prepare_input_text` concatenates text parts + image URLs for deterministic blake3 hashing
    - [ ] `fabricatio-router` PyO3: `completion_v(send_to, text, images: Option<Vec<Vec<u8>>>)` — raw bytes → base64
      data URIs, MIME sniffing, construct `ContentPart` list
    - [ ] Python `UseLLM.aaskv(text: str | list[str], images: bytes | list[bytes] | None)` — clean interface, no
      `ContentPart` exposure
    - [ ] Tests: text-only backward compat, single image, multi-image, batch mode
- [x] Introduce Variant-based llm select, standardize llm calling procedure, which can reduce the config of the model
  needed
