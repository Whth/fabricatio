use crate::deployment::Deployment;
use crate::model::{CompletionModel, EmbeddingModel, Model};
use crate::provider::Provider;
use crate::PersistentCache;
use once_cell::sync::Lazy;
use std::marker::PhantomData;
use std::sync::Arc;
use tokio::sync::Mutex;

struct Router<Tag: ModelTypeTag> {
    cache: Option<PersistentCache>,
    providers: Vec<Arc<dyn Provider>>,
    deployments: Vec<Arc<Mutex<Deployment<Tag::Model>>>>,
    _marker: PhantomData<Tag>,
}

impl<Tag: ModelTypeTag> Default for Router<Tag> {
    fn default() -> Self {
        Self {
            cache: None,
            providers: vec![],
            deployments: vec![],
            _marker: PhantomData,
        }
    }
}


trait ModelTypeTag {
    type Model: ?Sized + Model;
}


#[derive(Default)]
struct CompletionTag;
#[derive(Default)]
struct EmbeddingTag;
// CompletionTag 关联的是 dyn CompletionModel
impl ModelTypeTag for CompletionTag {
    type Model = dyn CompletionModel;
}

// EmbeddingTag 关联的是 dyn EmbeddingModel
impl ModelTypeTag for EmbeddingTag {
    type Model = dyn EmbeddingModel;
}


pub static COMPLETION_MODEL_ROUTER: Lazy<Router<CompletionTag>> = Lazy::new(
    || {
        Router::default()
    }
);

pub static EMBEDDING_MODEL_ROUTER: Lazy<Router<CompletionTag>> = Lazy::new(
    || {
        Router::default()
    }
);