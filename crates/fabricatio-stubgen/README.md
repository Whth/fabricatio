# Fabricatio Stubgen

A specialized Python stub generation tool for the Fabricatio ecosystem, automatically generating `.pyi` type stub files for Rust packages using PyO3 bindings and the pyo3-stub-gen framework.

## Overview

This crate provides automated generation of Python type stub files (`.pyi`) for Rust packages in the Fabricatio ecosystem. It leverages the `pyo3-stub-gen` library to create type annotations that enable better IDE support and type checking for Python code that interacts with Rust components.

## Features

### 🤖 Automated Stub Generation
- **Automatic Discovery**: Scans fabricatio packages for PyO3 bindings
- **Type Annotation Generation**: Creates comprehensive `.pyi` files with full type information
- **Cross-Package Support**: Handles multiple fabricatio packages in a single run

### 📦 Supported Packages
- `fabricatio-core`: Core functionality and base types
- `fabricatio-memory`: Memory management and data structures
- `fabricatio-diff`: Diff operations and comparison utilities

### 🔧 PyO3 Integration
- **Rust Bindings**: Generates stubs from actual PyO3 class definitions
- **Method Signatures**: Preserves exact method signatures and parameter types
- **Property Support**: Handles both readonly and readwrite properties

## Usage

### Basic Usage

```bash
# Generate stubs for all fabricatio packages
cargo run --bin fabricatio-stubgen
```

This will generate `.pyi` files in the Python package directories:

```
packages/
├── fabricatio-core/
│   ├── python/
│   │   └── fabricatio_core/
│   │       └── rust.pyi          # Generated stub file
│   └── src/lib.rs
├── fabricatio-memory/
│   ├── python/
│   │   └── fabricatio_memory/
│   │       └── rust.pyi          # Generated stub file
│   └── src/lib.rs
└── fabricatio-diff/
    ├── python/
    │   └── fabricatio_diff/
    │       └── rust.pyi          # Generated stub file
    └── src/lib.rs
```

### Generated Stub Structure

The generated `.pyi` files provide type information for:

```python
# Example generated stub content
from typing import Optional, List, Dict, Any
from fabricatio_config import Config, LLMConfig, EmbeddingConfig

class Core:
    def __init__(self, config: Config) -> None: ...
    
    def process_task(self, task: str, **kwargs) -> Dict[str, Any]: ...
    
    @property
    def config(self) -> Config: ...
    
    def set_llm_config(self, llm_config: LLMConfig) -> None: ...

class Memory:
    def __init__(self) -> None: ...
    
    def store(self, key: str, value: Any) -> None: ...
    
    def retrieve(self, key: str) -> Optional[Any]: ...
    
    def clear(self) -> None: ...

class Diff:
    def __init__(self, config: Config) -> None: ...
    
    def create_diff(self, old: str, new: str) -> Dict[str, Any]: ...
    
    def apply_diff(self, content: str, diff: Dict[str, Any]) -> str: ...
```

### Integration with Python Code

With generated stubs, Python IDEs can provide:

- **Autocompletion**: Full method and property suggestions
- **Type Checking**: Static analysis with mypy or similar tools
- **Documentation**: Parameter types and return types in tooltips
- **Error Detection**: Catch type mismatches at development time

```python
from fabricatio_core import Core
from fabricatio_config import Config

# Full IDE support with type information
config = Config()
core = Core(config)

# Autocomplete works for all methods
core.process_task  # Shows: process_task(task: str, **kwargs) -> Dict[str, Any]

# Type checking ensures correct usage
result: Dict[str, Any] = core.process_task("analyze_code")  # ✓ Valid
invalid = core.process_task(123)  # ✗ Type error: expected str, got int
```

## Architecture

### Build Process

1. **Discovery**: The tool scans for fabricatio packages with PyO3 bindings
2. **Generation**: Uses `pyo3-stub-gen` to analyze Rust code and generate stubs
3. **Output**: Writes generated `.pyi` files to appropriate Python package directories

### Dependencies

- `pyo3-stub-gen`: Core stub generation functionality
- `fabricatio-core`: Core package with PyO3 bindings
- `fabricatio-memory`: Memory management package
- `fabricatio-diff`: Diff operations package
- `pyo3-build-config`: Python extension build configuration

### Build Configuration

The `build.rs` file configures the Python extension build process:

```rust
fn main() {
    pyo3_build_config::add_extension_module_link_args();
    pyo3_build_config::add_python_framework_link_args();
}
```

## Development Workflow

### Regenerating Stubs

When Rust code changes affect PyO3 bindings, regenerate stubs:

```bash
# After modifying Rust code
cargo build
cargo run --bin fabricatio-stubgen
```

### Version Management

The stubgen crate uses semantic versioning:
- **Patch versions**: Bug fixes and minor improvements
- **Minor versions**: New packages or major API additions
- **Major versions**: Breaking changes in stub generation

## Benefits

### For Developers
- **Better IDE Experience**: Full autocompletion and type information
- **Early Error Detection**: Static type checking catches bugs early
- **Documentation**: Type signatures serve as inline documentation
- **Refactoring Safety**: Type system prevents breaking changes

### For Users
- **IntelliSense**: Rich autocompletion in IDEs
- **Type Safety**: Catch errors before runtime
- **Documentation**: Hover tooltips show parameter types
- **API Clarity**: Clear method signatures and return types

## Examples

See the `examples` directory for complete demonstrations of:
- Stub generation from Rust PyO3 code
- Python usage with type annotations
- IDE integration and type checking workflows

## License

This crate is part of the Fabricatio project and follows the same licensing terms.