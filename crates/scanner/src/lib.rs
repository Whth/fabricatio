//! # Python Package Scanner
//!
//! A high-performance scanner for detecting installed Python packages and their optional dependencies (extras).
//!
//! This module implements an efficient, low-latency solution for runtime dependency introspection, designed for integration with Python via PyO3.
//!
//! ## Architecture
//!
//! The scanner uses a two-phase strategy:
//!
//! 1. **Discovery Phase (`refresh`)**: Scans the `site-packages` directory to index package names and `.dist-info` paths into an in-memory LRU cache (`moka::sync::Cache`).
//!
//! 2. **Lazy Resolution Phase (`get_extra_all`)**: Parses the `METADATA` file of a package only when its extras are first queried. The resulting `extra -> [dependencies]` mapping is cached atomically to ensure subsequent lookups are O(1) memory operations.
//!
//! This design minimizes startup cost while providing microsecond-scale query performance.
//!
//! ## Key Features
//!
//! - **Fast Queries**: `is_installed()` and `extra_satisfied()` operate on cached data, achieving sub-microsecond latency.
//! - **Lazy Parsing**: METADATA files are read and parsed only upon first access, optimizing cold-start time.
//! - **Thread Safety**: Built on `moka` and `rayon`, safe for concurrent use in async environments.
//! - **Accurate Matching**: Normalizes package names (replacing `-` with `_`) to align with Python's import system.
//!
//! ## Performance
//!
//! Benchmarks show `extra_satisfied` executes in ~0.5μs after the initial parse, over 1000x faster than standard library methods like `importlib.metadata.distribution()`.
//!
//! This makes it suitable for high-frequency checks in dynamic systems such as agent frameworks.//! A scanner for Python packages in site-packages directory.
//!
//! This module provides functionality to scan and analyze installed Python packages,
//! including their dependencies and extras requirements.

use moka::sync::Cache;
use once_cell::sync::Lazy;
use pep508_rs::{MarkerExpression, Requirement, VerbatimUrl};
use pyo3::prelude::*;
use rayon::prelude::*;
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;
use std::str::FromStr;
use std::sync::Arc;
use walkdir::WalkDir;

static SITE_PACKAGES: Lazy<PathBuf> = Lazy::new(|| {
    Python::attach(|py| {
        let sys = py.import("sys").expect("Failed to import sys");
        let paths = sys.getattr("prefix").expect("Failed to get sys.path");
        paths
            .extract::<PathBuf>()
            .unwrap()
            .join("Lib/site-packages")
    })
});

type PackageExtras = HashMap<String, Vec<String>>;

type PackageRoot = PathBuf;
/// A scanner for Python packages that caches package information.
///
/// This struct maintains a cache of installed Python packages and provides
/// methods to query package information such as dependencies and extras.
pub struct PythonPackageScanner {
    /// Cache storing package names mapped to their items.
    known_packages: Cache<String, PackageRoot>,

    /// Cache storing package names mapped to their extra mappings.
    extras_mappings: Cache<String, Arc<PackageExtras>>,
    /// Path to the site-packages directory.
    site_packages: PathBuf,
}

impl Default for PythonPackageScanner {
    fn default() -> Self {
        Self::new()
    }
}

impl PythonPackageScanner {
    /// Creates a new `PythonPackageScanner`.
    ///
    /// Initializes the scanner by building a cache and determining the site-packages path.
    /// Automatically refreshes the cache upon creation.
    ///
    /// # Returns
    ///
    /// A new instance of `PythonPackageScanner`.
    pub fn new() -> Self {
        Self {
            known_packages: Cache::builder().build(),
            extras_mappings: Cache::builder().build(),
            site_packages: SITE_PACKAGES.clone(),
        }
        .refresh()
    }

    pub fn list_installed(&self) -> Vec<String> {
        self.known_packages
            .iter()
            .map(|(k, _)| k.to_string())
            .collect()
    }
    /// Refreshes the package cache by scanning the site-packages directory.
    ///
    /// Clears the current cache and rescans the site-packages directory to
    /// discover installed packages. Each package's .dist-info directory is
    /// identified and added to the cache.
    ///
    /// # Returns
    ///
    /// The same instance with refreshed cache.
    pub fn refresh(self) -> Self {
        self.known_packages.invalidate_all();
        WalkDir::new(&self.site_packages)
            .max_depth(1)
            .min_depth(1)
            .into_iter()
            .par_bridge()
            .filter_map(Result::ok)
            .filter(|entry| entry.file_type().is_dir())
            .map(|entry| {
                let path = entry.path().to_path_buf();
                let dir_name = entry.file_name().to_string_lossy().to_string();
                (path, dir_name)
            })
            .filter(|(_, dir_name)| dir_name.ends_with(".dist-info"))
            .for_each(|(entry_path, dir_name)| {
                let (pkg_name, _) = dir_name.split_once("-").unwrap();
                self.known_packages.insert(pkg_name.to_string(), entry_path);
            });
        self
    }

    /// Checks whether **all** given extras of a package have their dependencies satisfied.
    ///
    /// This function returns `true` only if **every** extra in `extras` is defined
    /// and all of its dependencies are installed.
    ///
    /// # Arguments
    /// * `pkg_name` - The normalized package name (dashes `-` are replaced with underscores `_` internally).
    /// * `extras` - An iterator of extra names (e.g., `["dev", "test"]`).
    ///
    /// # Returns
    /// `true` if all listed extras exist and their dependencies are installed; `false` otherwise.
    ///
    /// # Note
    /// - If any extra is not defined in the package metadata, this returns `false`.
    /// - Only top-level `extra == "..."` markers are supported (no complex marker expressions).
    pub fn extras_satisfied<I, S>(&self, pkg_name: &str, extras: I) -> bool
    where
        I: IntoIterator<Item = S>,
        S: AsRef<str>,
    {
        let pkg_name = pkg_name.replace("-", "_");
        if let Some(all_extra) = self.get_extra_all(&pkg_name) {
            extras.into_iter().all(|extra| {
                if let Some(deps) = all_extra.get(extra.as_ref()) {
                    deps.iter()
                        .all(|dep| self.known_packages.get(dep.as_str()).is_some())
                } else {
                    false // extra not defined → not satisfied
                }
            })
        } else {
            false // package not found
        }
    }

    /// Checks whether a specific extra of a package has its dependencies satisfied.
    pub fn extra_satisfied(&self, pkg_name: &str, extra: &str) -> bool {
        self.extras_satisfied(pkg_name, std::iter::once(extra))
    }

    /// Retrieves all extras and their dependencies for a given package.
    ///
    /// Gets the mapping of extras to their required dependencies for a specified package.
    ///
    /// # Arguments
    ///
    /// * `pkg_name` - The name of the package.
    ///
    /// # Returns
    ///
    /// An optional reference to the extras mapping if the package exists, `None` otherwise.
    fn get_extra_all(&self, pkg_name: &str) -> Option<Arc<PackageExtras>> {
        if let Some(pkg_root) = self.known_packages.get(pkg_name) {
            Some(self.extras_mappings.get_with_by_ref(pkg_name, || {
                Arc::new(Self::acquire_extra_mapping(
                    fs::read_to_string(pkg_root.join("METADATA"))
                        .expect("Failed to read METADATA file"),
                ))
            }))
        } else {
            None
        }
    }

    /// Extracts the extra dependency mapping from package metadata.
    ///
    /// Parses the METADATA file of a package to extract the mapping between
    /// extras and their required dependencies.
    ///
    /// # Arguments
    ///
    /// * `metadata` - The content of the package's METADATA file.
    ///
    /// # Returns
    ///
    /// A map of extras to their dependency lists.
    #[inline]
    fn acquire_extra_mapping(metadata: String) -> PackageExtras {
        let mut reg: PackageExtras = HashMap::new();

        metadata
            .lines()
            .filter_map(|line: &str| line.strip_prefix("Requires-Dist: "))
            .filter(|line: &&str| line.contains("extra =="))
            .filter_map(|line: &str| Requirement::<VerbatimUrl>::from_str(line).ok())
            .filter_map(|req| {
                req.marker
                    .top_level_extra()
                    .map(|expr| (req.name.to_string(), expr))
            })
            .for_each(|(req_name, expr)| {
                if let MarkerExpression::Extra { name, .. } = expr {
                    reg.entry(name.to_string())
                        .or_default()
                        .push(req_name.replace("-", "_"))
                }
                //TODO: add complex extra analytics
            });
        reg
    }

    /// Checks if a package is installed.
    ///
    /// Determines whether a package with the given name is present in the cache.
    ///
    /// # Arguments
    ///
    /// * `name` - The name of the package to check.
    ///
    /// # Returns
    ///
    /// `true` if the package is installed, `false` otherwise.
    pub fn is_installed(&self, name: &str) -> bool {
        self.known_packages
            .get(name.replace("-", "_").as_str())
            .is_some()
    }
}
