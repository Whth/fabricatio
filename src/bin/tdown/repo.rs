use octocrab::repos::RepoHandler;
use once_cell::sync::Lazy;
use std::sync::Arc;

use fabricatio_constants::{REPO_NAME, REPO_OWNER};

static OCT_INSTANCE: Lazy<Arc<octocrab::Octocrab>> = Lazy::new(octocrab::instance);

static REPO: Lazy<RepoHandler> = Lazy::new(|| OCT_INSTANCE.repos(REPO_OWNER, REPO_NAME));
