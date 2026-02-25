use serde::{Deserialize, Serialize};
use strum::{Display, EnumString};

/// Represents the role of a message sender in a conversation.
///
/// Only three standard roles are supported: `user`, `system`, and `assistant`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Display, EnumString)]
#[serde(rename_all = "lowercase")]
#[strum(serialize_all = "lowercase")]
pub enum Role {
    User,
    System,
    Assistant,
}

/// A single message in a conversation.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Message {
    pub role: Role,
    pub content: String,
}

impl Message {
    /// Creates a new message with the given role and content.
    pub fn new(role: Role, content: String) -> Self {
        Self { role, content }
    }
}

/// A list of messages supporting method chaining for fluent construction.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Messages {
    messages: Vec<Message>,
}

impl Messages {
    /// Creates a new empty `Messages` instance.
    pub fn new() -> Self {
        Self::default()
    }

    /// Adds a message with the specified role and content.
    ///
    /// If the content is empty, the message is not added.
    ///
    /// # Arguments
    ///
    /// * `role` - The role of the sender (`User`, `System`, or `Assistant`).
    /// * `content` - The message content.
    ///
    /// # Returns
    ///
    /// A mutable reference to `self` for method chaining.
    pub fn add_message(&mut self, role: Role, content: String) -> &mut Self {
        if !content.is_empty() {
            self.messages.push(Message::new(role, content));
        }
        self
    }

    /// Adds a user message.
    pub fn add_user_message(&mut self, content: String) -> &mut Self {
        self.add_message(Role::User, content)
    }

    /// Adds a system message.
    pub fn add_system_message(&mut self, content: String) -> &mut Self {
        self.add_message(Role::System, content)
    }

    /// Adds an assistant message.
    pub fn add_assistant_message(&mut self, content: String) -> &mut Self {
        self.add_message(Role::Assistant, content)
    }

    pub fn export(self) -> Vec<Message> {
        self.messages
    }
}
