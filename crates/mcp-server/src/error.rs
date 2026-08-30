use thiserror::Error;

/// Represents possible errors that can occur in MCP server operations
#[derive(Debug, Error)]
pub enum ServerError {
    /// I/O related errors
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    /// Errors originating from RMCP operations
    #[error("RMCP error: {0}")]
    RmcpError(#[from] rmcp::ServiceError),

    /// Server initialization errors
    #[error("Server initialization error: {0}")]
    ServerInitError(#[from] Box<rmcp::service::ServerInitializeError>),

    /// The tool schema could not be parsed as a JSON object
    #[error("Invalid tool schema for {0}: {1}")]
    InvalidSchema(String, String),

    /// The tool does not exist in the registry
    #[error("Tool {0} not found")]
    ToolNotFound(String),

    /// The server task failed or was aborted
    #[error("Server task failed: {0}")]
    TaskError(String),
}
/// Result type alias for MCP server operations
pub type Result<T> = std::result::Result<T, ServerError>;
