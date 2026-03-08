use crate::deployment::Deployment;
use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model};
use crate::provider::Provider;
use crate::{PersistentCache, ThrydError};
use crate::{Result, SEPARATE};
use once_cell::sync::Lazy;
use std::collections::{BTreeMap, HashMap, HashSet};
use std::marker::PhantomData;
use std::sync::Arc;


type DeploymentIdentifier = String;
type ProviderName = String;
type ModelName = String;

struct Router<Tag: ModelTypeTag> {
    cache: Option<PersistentCache>,
    providers: HashMap<ProviderName, Arc<dyn Provider>>,
    deployments: BTreeMap<DeploymentIdentifier, Deployment<Tag::Model>>,
    _marker: PhantomData<Tag>,
}


impl<Tag: ModelTypeTag> Router<Tag> {
    pub fn add_provider<P: Provider + 'static>(&mut self, provider: P) -> Result<&mut Self> {
        self.providers.try_insert(
            provider.provider_name().to_string(),
            Arc::new(provider),
        ).map_err(
            |e|
                ThrydError::Router(format!("Provider with `{}` is already added.", e.entry.key()))
        )?;
        Ok(self)
    }


    pub fn add_or_update_provider<P: Provider + 'static>(&mut self, provider: P) -> Result<&mut Self> {
        if self.providers.contains_key(provider.provider_name()) {
            self.remove_provider(&provider.provider_name())?;
        }
        self.add_provider(provider)
    }


    pub fn remove_provider(&mut self, provider_name: &str) -> Result<&mut Self> {
        self.providers.remove(provider_name).ok_or_else(
            || ThrydError::Router(format!("Provider with `{}` is not added.", provider_name))
        )?;
        Ok(self)
    }

    pub fn add_or_ok_provider<P: Provider + 'static>(
        &mut self, provider: P,
    ) -> Result<&mut Self> {
        if self.providers.contains_key(provider.provider_name()) {
            Ok(self)
        } else {
            self.add_provider(provider)
        }
    }


    pub fn add_deployment(&mut self, deployment: Deployment<Tag::Model>) -> Result<&mut Self> {
        self.deployments.try_insert(
            deployment.identifier(),
            deployment,
        ).map_err(
            |e|
                ThrydError::Router(format!("Deployment with `{}` is already added.", e.entry.key()))
        )?;
        Ok(self)
    }


    pub fn add_or_update_deployment(&mut self, deployment: Deployment<Tag::Model>) -> Result<&mut Self> {
        if self.deployments.contains_key(&deployment.identifier()) {
            self.remove_deployment(&deployment.identifier())?;
        }
        self.add_deployment(deployment)
    }

    pub fn add_or_ok_deployment(&mut self, deployment: Deployment<Tag::Model>) -> Result<&mut Self> {
        if self.deployments.contains_key(&deployment.identifier()) {
            Ok(self)
        } else {
            self.add_deployment(deployment)
        }
    }

    pub fn remove_deployment(&mut self, identifier: &str) -> Result<&mut Self> {
        self.deployments.remove(identifier).ok_or_else(
            || ThrydError::Router(format!("Deployment with `{}` is not added.", identifier))
        )?;
        Ok(self)
    }
}


impl<Tag: ModelTypeTag> Router<Tag> {
    fn analyze_identifier(identifier: String) -> Result<(ProviderName, ModelName)> {
        identifier.split_once(SEPARATE)
            .ok_or_else(||

                ThrydError::Router(format!("Invalid identifier `{}`", identifier))
            ).map(
            |(provider_name, model_name)| (provider_name.to_string(), model_name.to_string())
        )
    }
}


impl Router<CompletionTag> {
    pub fn completion(&self, send_to: DeploymentIdentifier, request: CompletionRequest) -> Result<String> {
        todo!()
    }
}


impl Router<EmbeddingTag> {
    pub fn embedding(&self, send_to: DeploymentIdentifier, request: EmbeddingRequest) -> Result<Vec<f32>> {
        todo!()
    }
}


impl<Tag: ModelTypeTag> Default for Router<Tag> {
    fn default() -> Self {
        Self {
            cache: None,
            providers: HashSet::default(),
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