use crate::deployment::Deployment;
use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, Model};
use crate::utils::am;
use crate::Result;
use crate::{PersistentCache, ThrydError};
use once_cell::sync::Lazy;
use std::collections::BTreeMap;
use std::marker::PhantomData;
use std::sync::Arc;
use tokio::sync::Mutex;
struct Router<Tag: ModelTypeTag> {
    cache: Option<PersistentCache>,
    deployments: BTreeMap<String, Arc<Mutex<Deployment<Tag::Model>>>>,
    _marker: PhantomData<Tag>,
}


impl<Tag: ModelTypeTag> Router<Tag> {
    pub fn add_deployment(&mut self, deployment: Deployment<Tag::Model>) -> Result<&mut Self> {
        self.deployments.try_insert(
            deployment.identifier(), am(deployment),
        ).map_err(
            |e| ThrydError::Router(format!("Deployment with `{}` is already added.", e.entry.key()))
        )?;
        Ok(self)
    }

    pub fn remove_deployment(&mut self, identifier: &str) -> Result<&mut Self> {
        self.deployments.remove(identifier).ok_or_else(
            || ThrydError::Router(format!("Deployment with `{}` is not added.", identifier))
        )?;
        Ok(self)
    }
}


impl Router<CompletionTag> {
    pub fn completion(&self, send_to: String, request: CompletionRequest) -> Result<String> {
        todo!()
    }
}


impl<Tag: ModelTypeTag> Default for Router<Tag> {
    fn default() -> Self {
        Self {
            cache: None,
            deployments: BTreeMap::default(),
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
impl ModelTypeTag for CompletionTag {
    type Model = dyn CompletionModel;
}

impl ModelTypeTag for EmbeddingTag {
    type Model = dyn EmbeddingModel;
}


pub static COMPLETION_MODEL_ROUTER: Lazy<Router<CompletionTag>> = Lazy::new(
    || {
        Router::default()
    }
);

pub static EMBEDDING_MODEL_ROUTER: Lazy<Router<EmbeddingTag>> = Lazy::new(
    || {
        Router::default()
    }
);