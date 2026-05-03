---
description: Add a new package to stubgen
---

## Steps

### 1. Add dependency to `crates/fabricatio-stubgen/Cargo.toml`

Add the package dependency under `[dependencies]`:
```toml
fabricatio-<name> = { path = "../../packages/fabricatio-<name>", default-features = false, optional = true }
```

### 2. Add feature to `crates/fabricatio-stubgen/Cargo.toml`

**In the `[features]` `all` list**, add:
```toml
"<name>"
```

**Add feature line** under the existing features:
```toml
<name> = ["fabricatio-<name>/stubgen"]
```

### 3. Add stub generation call to `crates/fabricatio-stubgen/src/main.rs`

Add before `Ok(())`:
```rust
#[cfg(feature = "<name>")]
fabricatio_<name>::stub_info()?.generate()?;
```

### 4. Fix PyO3 API compatibility in the package's `src/lib.rs`

If using `Python::with_gil`, replace with:
```rust
// SAFETY: GIL is held during module initialization
let py = unsafe { Python::assume_attached() };
```

### 5. Add required dependencies to the package's `Cargo.toml`

Common needed:
- `url = "2.5.8"` (for URL parsing)

### 6. Run stubgen

```bash
cd crates/fabricatio-stubgen && cargo run --bin fabricatio-stubgen --features <name>
```

### 7. Verify the stub

Check that `packages/fabricatio-<name>/python/fabricatio_<name>/rust/__init__.pyi` was generated.

### 8. Commit
