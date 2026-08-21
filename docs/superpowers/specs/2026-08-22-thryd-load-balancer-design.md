# Thryd Load-Balancer Design

- **Date**: 2026-08-22
- **Status**: Proposed
- **Scope**: `crates/thryd` (strategy + enum), `crates/fabricatio-config` (config field), `crates/fabricatio-router` (wiring), stubs

## Problem

`Router::wait_for_any` (`crates/thryd/src/route/mod.rs:386`) scans a group's deployments in
insertion order and picks the first deployment whose projected cooldown is zero. When nothing is
rate-limited — the common case — every request lands on the first deployment until it saturates;
traffic only spills to later deployments once earlier ones develop cooldown. Selection is fully
predictable (fill-first), so multiple deployments in one group never share load evenly.

## Decision

Introduce a pluggable, runtime-switchable balancer on the router:

```rust
// thryd::route (re-exported at crate root)
#[derive(EnumString, Debug, Clone, Copy, Deserialize, Serialize, Default)]
#[serde(rename_all = "snake_case")]
#[cfg_attr(feature = "stubgen", pyo3_stub_gen::derive::gen_stub_pyclass_enum)]
#[cfg_attr(feature = "pyo3", pyo3::pyclass(from_py_object))]
pub enum Balancer {
    /// Legacy behavior: first deployment with zero cooldown wins.
    FirstAvailable,
    /// Rotate through available deployments (default).
    #[default]
    RoundRobin,
    /// Pick randomly, weighted by each deployment's remaining quota capacity.
    WeightedRandom,
}
```

Default is `RoundRobin`. The user chose the pluggable design over a single fixed strategy to allow
experimenting; least-utilization may be added later if proportional sharing proves necessary.

## Configuration surface (Python side)

One global field on `RoutingConfig`, mirroring how `retry_*` settings work:

```rust
/// Load-balancing strategy applied across each group's deployments.
/// `None` falls back to the thryd default (`RoundRobin`).
pub balancer: Option<Balancer>,
```

User-facing TOML (`fabricatio.toml`; env `FABRICATIO__ROUTING__BALANCER=…` and
`pyproject.toml `[tool.fabricatio.routing]`` behave identically through the existing figment stack):

```toml
[routing]
balancer = "round_robin"   # "first_available" | "round_robin" | "weighted_random"
```

An unknown string fails at config load with serde's "unknown variant" error. The enum lives in
thryd and is reused by fabricatio-config exactly like the existing `ProviderType` precedent
(`EnumString` + serde + pyclass + stub-gen). `.pyi` stubs regenerate via the `stubgen` feature.

The setting is **global** (applied to all three routers: completion, embedding, reranker).
Per-group overrides are a non-goal for now.

## Router changes

```rust
pub struct Router<Tag> {
    // ...existing fields...
    balancer: Balancer,
    rr_counters: DashMap<RouteGroupName, AtomicUsize>, // RoundRobin state per group
    rng_state: AtomicU64,                              // WeightedRandom xorshift* state
}

impl Router<Tag> {
    pub fn with_balancer(self, balancer: Balancer) -> Self;   // builder style, like with_retry
    pub fn set_balancer(&self, balancer: Balancer);           // runtime switch
}
```

### Selection seam

`wait_for_any` keeps its single scan over the group. Today it `break`s on the first zero-cooldown
deployment; instead it now collects all deployments with `min_cooldown_time(token_count) == 0`,
then delegates to the active strategy:

- **FirstAvailable** → `available[0]` (byte-for-byte today's outcome; the early `break` disappears,
  costing an O(n) scan of small groups against 100 ms+ LLM calls — negligible).
- **RoundRobin** → counter value mod `available.len()`, then increment. Counter always taken modulo
  the *current* length, so undeploy/redeploy never desyncs it. Counters are removed together with
  their group in `remove_group`.
- **WeightedRandom** → weight per deployment:
  `w = clamp(rpm_remaining_frac, eps..1] * clamp(tpm_remaining_frac, eps..1])`, where a missing
  RPM/TPM quota contributes factor `1`. Weights are read from the deployment's `UsageTracker`
  (small getters to add on `Deployment`, e.g. `remaining_rpm_frac()` / `remaining_tpm_frac()`).
  Equal weights degenerate to uniform random. PRNG: hand-rolled `xorshift*` seeded from
  `current_timestamp()`, state in `AtomicU64` — no new dependency.

Fallback path is unchanged: when no deployment has zero cooldown, select the minimum projected
wait time exactly as today. Empty group / no-deployment errors are unchanged.

## Error handling

- Unknown config value → figment/serde failure at `Config::new()` time, before any routing exists.
- Strategy selection cannot fail; every strategy receives a non-empty `available` list or is not
  consulted (fallback branch).

## Testing

1. **FirstAvailable parity**: group of dummy deployments, all idle → always index 0 selected.
2. **RoundRobin rotation**: k requests over n available dummies → each selected floor(k/n) or
   ceil(k/n) times, in rotation order; survives undeploy/redeploy without panics or skips.
3. **WeightedRandom skew**: two deployments, one with ~10x remaining TPM fraction → over a few
   hundred draws the larger-capacity one wins ≥ 70% (statistical bound with tolerance; PRNG
   seeds from wall clock); equal quotas → near-uniform.
4. **Fallback unchanged**: all deployments saturated → min projected wait chosen (existing test
   coverage extended to run under each strategy).
5. **Config round-trip**: `"round_robin"` / `"weighted_random"` / `"first_available"` deserialize
   into the enum; unknown string errors; `None` → default RoundRobin reaches the built routers
   (fabricatio-router builder test or manual verification via `fabricatio_core.rust.CONFIG`).

## Non-goals

- Per-group or per-deployment strategy overrides.
- Least-utilization / P2C strategies (future additions to the same enum if needed).
- Latency-aware or health-check-based balancing (no data source exists today).
