use crate::deployment::Deployment;
use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model};
use crate::provider::{ProvideCompletionModel, ProvideEmbeddingModel, Provider};
use crate::{PersistentCache, ThrydError};
use crate::{Result, SEPARATE};
use once_cell::sync::Lazy;
use std::collections::{BTreeMap, HashMap};
use std::sync::Arc;


type DeploymentIdentifier = String;
type ProviderName = String;
type ModelName = String;

struct Router<Tag: ModelTypeTag> {
    cache: Option<PersistentCache>,
    providers: HashMap<ProviderName, Arc<Tag::Provider>>,
    deployments: BTreeMap<DeploymentIdentifier, Deployment<Tag::Model>>,
}


impl<Tag: ModelTypeTag> Router<Tag> {
    pub fn add_provider(&mut self, provider: Arc<Tag::Provider>) -> Result<&mut Self>
    {
        self.providers.try_insert(
            provider.provider_name().to_string(),
            provider,
        ).map_err(
            |e|
                ThrydError::Router(format!("Provider with `{}` is already added.", e.entry.key()))
        )?;
        Ok(self)
    }


    pub fn add_or_update_provider(&mut self, provider: Arc<Tag::Provider>) -> Result<&mut Self> {
        if self.providers.contains_key(provider.provider_name()) {
            self.remove_provider(provider.provider_name())?;
        }
        self.add_provider(provider)
    }


    pub fn remove_provider(&mut self, provider_name: &str) -> Result<&mut Self> {
        self.providers.remove(provider_name).ok_or_else(
            || ThrydError::Router(format!("Provider with `{}` is not added.", provider_name))
        )?;
        Ok(self)
    }

    pub fn add_or_ok_provider(
        &mut self, provider: Arc<Tag::Provider>,
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
    pub async fn completion(&self, send_to: DeploymentIdentifier, request: CompletionRequest) -> Result<String> {
        self.get_deployment(send_to)?.wait_capacity_for(request.message.to_string())
            .await?
            .completion(request).await
    }

    fn get_provider(&self, provider_name: ProviderName) -> Result<Arc<dyn ProvideCompletionModel>> {
        self.providers.get(provider_name.as_str()).ok_or_else(
            || ThrydError::Router(format!("Provider with `{}` is not added.", provider_name))
        ).cloned()
    }


    fn get_deployment(&self, identifier: DeploymentIdentifier) -> Result<&Deployment<dyn CompletionModel>> {
        self.deployments.get(identifier.as_str()).ok_or_else(
            || ThrydError::Router(format!("Deployment with `{}` is not added.", identifier))
        )
    }

    fn create_deployment(&self, identifier: DeploymentIdentifier, rpm: Option<u32>, tpm: Option<u32>) -> Result<Deployment<dyn CompletionModel>>

    {
        let (provider_name, model_name) = Self::analyze_identifier(identifier)?;
        Ok(
            Deployment::new(
                self.get_provider(provider_name)?.create_completion_model(model_name)?
            ).with_usage_constrain(rpm, tpm)
        )
    }
}


impl Router<EmbeddingTag> {
    pub async fn embedding(&self, send_to: DeploymentIdentifier, request: EmbeddingRequest) -> Result<Vec<f32>> {
        self.get_deployment(send_to)?.wait_capacity_for(request.texts.join(""))
            .await?
            .embedding(request).await
    }
    fn get_provider(&self, provider_name: ProviderName) -> Result<Arc<dyn ProvideEmbeddingModel>> {
        self.providers.get(provider_name.as_str()).ok_or_else(
            || ThrydError::Router(format!("Provider with `{}` is not added.", provider_name))
        ).cloned()
    }


    fn get_deployment(&self, identifier: DeploymentIdentifier) -> Result<&Deployment<dyn EmbeddingModel>> {
        self.deployments.get(identifier.as_str()).ok_or_else(
            || ThrydError::Router(format!("Deployment with `{}` is not added.", identifier))
        )
    }

    fn create_deployment(&self, identifier: DeploymentIdentifier, rpm: Option<u32>, tpm: Option<u32>) -> Result<Deployment<dyn EmbeddingModel>>

    {
        let (provider_name, model_name) = Self::analyze_identifier(identifier)?;
        Ok(
            Deployment::new(
                self.get_provider(provider_name)?.create_embedding_model(model_name)?
            ).with_usage_constrain(rpm, tpm)
        )
    }
}


impl<Tag: ModelTypeTag> Default for Router<Tag> {
    fn default() -> Self {
        Self {
            cache: None,
            providers: HashMap::default(),
            deployments: BTreeMap::default(),
        }
    }
}


trait ModelTypeTag {
    type Model: ?Sized + Model;

    type Provider: ?Sized + Provider;
}


#[derive(Default)]
struct CompletionTag;
#[derive(Default)]
struct EmbeddingTag;
impl ModelTypeTag for CompletionTag {
    type Model = dyn CompletionModel;
    type Provider = dyn ProvideCompletionModel;
}

impl ModelTypeTag for EmbeddingTag {
    type Model = dyn EmbeddingModel;
    type Provider = dyn ProvideEmbeddingModel;
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