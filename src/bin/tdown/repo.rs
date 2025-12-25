use fabricatio_constants::{REPO_NAME, REPO_OWNER};
use octocrab::repos::RepoHandler;
use once_cell::sync::Lazy;
use std::sync::Arc;
pub static OCT_INSTANCE: Lazy<Arc<octocrab::Octocrab>> = Lazy::new(octocrab::instance);

pub static REPO: Lazy<RepoHandler> = Lazy::new(|| OCT_INSTANCE.repos(REPO_OWNER, REPO_NAME));
