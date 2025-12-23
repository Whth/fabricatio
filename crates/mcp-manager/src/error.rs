use thiserror::Error;

/// Represents possible errors that can occur in MCP operations
#[derive(Debug, Error)]
pub enum McpError {
    /// I/O related errors
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    /// Errors originating from RMCP operations
    #[error("RMCP error: {0}")]
    RmcpError(#[from] rmcp::ServiceError),

    /// Requested client not found
    #[error("Client {0} not found")]
    ClientNotFound(String),

    /// Service initialization error
    #[error("Service initialization error: {0}")]
    ServiceInitError(String),

    #[error("Service not supported")]
    ServiceNotSupportedError,

    /// Command not found
    #[error("Command not found: {0}")]
    CommandNotFound(#[from] which::Error),

    /// Tool not found
    #[error("Tool not found: {0}")]
    ToolNotFound(String),
}
/// Result type alias for MCP operations
pub type Result<T> = std::result::Result<T, McpError>;

#[cfg(feature = "into_pyerr")]
impl McpError {
    pub fn into_pyerr(self) -> pyo3::PyErr {
        pyo3::exceptions::PyRuntimeError::new_err(self.to_string())
    }
}
