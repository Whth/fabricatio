use crate::deployment::Deployment;
use crate::model::{CompletionModel, CompletionRequest, EmbeddingModel, EmbeddingRequest, Model};
use crate::provider::Provider;
use crate::tracker::Quota;
use crate::{PersistentCache, ThrydError};
use crate::{Result, SEPARATE};
use async_trait::async_trait;
use dashmap::mapref::one::Ref;
use dashmap::DashMap;
use serde::de::DeserializeOwned;
use serde::Serialize;
use std::path::Path;
use std::sync::Arc;
use tracing::*;
pub type DeploymentIdentifier = String;
pub type RouteGroupName = String;
pub type ProviderName = String;
pub type ModelName = String;

pub type DeploymentEntry<Model> = Arc<Deployment<Model>>;

pub struct Router<Tag: ModelTypeTag> {
    cache: Option<PersistentCache>,
    providers: DashMap<ProviderName, Arc<dyn Provider>>,
    groups: DashMap<RouteGroupName, Vec<DeploymentEntry<Tag::Model>>>,
}

impl<Tag: ModelTypeTag> Router<Tag> {
    pub fn with_cache(database_file: impl AsRef<Path>) -> Result<Self> {
        Ok(Self {
            cache: Some(PersistentCache::create_or_open(database_file)?),
            ..Self::default()
        })
    }

    pub fn add_or_update_provider(&self, provider: Arc<dyn Provider>) -> &Self {
        debug!(
            "Insert provider `{}`, base_url: `{}`",
            provider.provider_name(),
            provider.endpoint()
        );
        self.providers
            .insert(provider.provider_name().to_string(), provider);
        self
    }

    pub fn remove_provider(&self, provider_name: &str) -> Result<&Self> {
        debug!("Removing provider `{}`", provider_name);
        self.providers.remove(provider_name).ok_or_else(|| {
            ThrydError::Router(format!("Provider with `{}` is not added.", provider_name))
        })?;
        Ok(self)
    }

    fn add_deployment(
        &self,
        group: RouteGroupName,
        deployment: Deployment<Tag::Model>,
    ) -> Result<&Self> {
        self.groups
            .entry(group)
            .or_default()
            .push(Arc::new(deployment));
        Ok(self)
    }

    fn remove_deployment(
        &self,
        group: &str,
        deployment_identifier: DeploymentIdentifier,
    ) -> Result<&Self> {
        self.groups
            .get_mut(group)
            .ok_or_else(|| {
                ThrydError::Router(format!("Group with name `{}` is not added.", group))
            })?
            .retain(|deployment| deployment.identifier() != deployment_identifier);
        Ok(self)
    }

    pub fn deploy(
        &self,
        group: RouteGroupName,
        deployment_identifier: DeploymentIdentifier,
        rpm: Option<Quota>,
        tpm: Option<Quota>,
    ) -> Result<&Self> {
        debug!("Deploying `{}` to group `{}`", deployment_identifier, group);
        let d = self.create_deployment(deployment_identifier, rpm, tpm)?;

        self.add_deployment(group, d)
    }

    pub fn undeploy(
        &self,
        group: RouteGroupName,
        deployment_identifier: DeploymentIdentifier,
    ) -> Result<&Self> {
        debug!(
            "Undeploying `{}` to group `{}`",
            deployment_identifier, group
        );

        self.remove_deployment(group.as_str(), deployment_identifier)
    }

    pub fn remove_group(&self, group: &str) -> Result<&Self> {
        self.groups.remove(group).ok_or_else(|| {
            ThrydError::Router(format!("Group with name `{}` is not added.", group))
        })?;

        Ok(self)
    }
    fn get_group(
        &self,
        group: RouteGroupName,
    ) -> Result<Ref<'_, RouteGroupName, Vec<DeploymentEntry<Tag::Model>>>> {
        self.groups
            .get(group.as_str())
            .ok_or_else(|| ThrydError::Router(format!("Group with name `{}` is not added.", group)))
    }
    async fn wait_for_any(
        &self,
        group: RouteGroupName,
        input_text: String,
    ) -> Result<DeploymentEntry<Tag::Model>> {
        let mut min_wait_time = u64::MAX;
        let mut d_ref: Option<DeploymentEntry<Tag::Model>> = None;

        let g = self.get_group(group.clone())?;

        for d in g.value() {
            let wait_time = d.min_cooldown_time(input_text.clone()).await;
            if wait_time == 0 {
                d_ref = Some(d.clone());
                break;
            } else if wait_time < min_wait_time {}
            {
                min_wait_time = wait_time;
                d_ref = Some(d.clone());
            }
        }

        d_ref.ok_or_else(|| {
            ThrydError::Router(format!("No deployment available for group `{}`", group))
        })
    }
    fn analyze_identifier(identifier: String) -> Result<(ProviderName, ModelName)> {
        identifier
            .split_once(SEPARATE)
            .ok_or_else(|| ThrydError::Router(format!("Invalid identifier `{}`", identifier)))
            .map(|(provider_name, model_name)| (provider_name.to_string(), model_name.to_string()))
    }

    fn create_deployment(
        &self,
        identifier: DeploymentIdentifier,
        rpm: Option<Quota>,
        tpm: Option<Quota>,
    ) -> Result<Deployment<Tag::Model>> {
        let (provider_name, model_name) = Self::analyze_identifier(identifier)?;
        debug!("Creating deployment for `{model_name}` of `{provider_name}`");
        Ok(Deployment::new(Tag::create_model(
            self.get_provider(provider_name)?,
            model_name,
        )?)
            .with_usage_constrain(rpm, tpm))
    }

    fn get_provider(&self, provider_name: ProviderName) -> Result<Arc<dyn Provider>> {
        self.providers
            .get(provider_name.as_str())
            .ok_or_else(|| {
                ThrydError::Router(format!("Provider with `{}` is not added.", provider_name))
            })
            .map(|p| p.value().clone())
    }

    pub async fn invoke(
        &self,
        send_to: RouteGroupName,
        request: Tag::Request,
    ) -> Result<Tag::Response> {
        debug!("Invoking route: {}", send_to);

        let d = self
            .wait_for_any(send_to, Tag::prepare_input_text(&request))
            .await?;

        if let Some(cache) = &self.cache {
            let key = Tag::prepare_cache_key(&request);

            if let Some(val) = cache.get_de::<Tag::Response>(key.as_str()) {
                debug!("Cache hit for: {key}");
                Ok(val)
            } else {
                debug!("Cache missed for: {key}");
                let res = Tag::execute_request(d, request).await?;
                cache.set_ser(key, &res)?;
                Ok(res)
            }
        } else {
            Tag::execute_request(d, request).await
        }
    }
}

impl<Tag: ModelTypeTag> Default for Router<Tag> {
    fn default() -> Self {
        Self {
            cache: None,
            providers: DashMap::default(),
            groups: DashMap::default(),
        }
    }
}

#[async_trait]
pub trait ModelTypeTag {
    type Model: ?Sized + Model;

    type Request;
    type Response: DeserializeOwned + Serialize + Clone;
    fn create_model(provider: Arc<dyn Provider>, model_name: ModelName)
                    -> Result<Box<Self::Model>>;

    fn prepare_input_text(request: &Self::Request) -> String;

    fn prepare_cache_key(request: &Self::Request) -> String {
        blake3::hash(Self::prepare_input_text(request).as_bytes()).to_string()
    }

    async fn execute_request(
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
    ) -> Result<Self::Response>;
}

#[derive(Default)]
pub struct CompletionTag;
#[derive(Default)]
pub struct EmbeddingTag;
#[async_trait]
impl ModelTypeTag for CompletionTag {
    type Model = dyn CompletionModel;
    type Request = CompletionRequest;
    type Response = String;

    fn create_model(
        provider: Arc<dyn Provider>,
        model_name: ModelName,
    ) -> Result<Box<Self::Model>> {
        provider.create_completion_model(model_name)
    }

    fn prepare_input_text(request: &Self::Request) -> String {
        request.message.to_string()
    }

    async fn execute_request(
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
    ) -> Result<Self::Response> {
        deployment.completion(request).await
    }
}

#[async_trait]
impl ModelTypeTag for EmbeddingTag {
    type Model = dyn EmbeddingModel;
    type Request = EmbeddingRequest;
    type Response = Vec<Vec<f32>>;

    fn create_model(
        provider: Arc<dyn Provider>,
        model_name: ModelName,
    ) -> Result<Box<Self::Model>> {
        provider.create_embedding_model(model_name)
    }

    fn prepare_input_text(request: &Self::Request) -> String {
        request.texts.concat()
    }

    async fn execute_request(
        deployment: Arc<Deployment<Self::Model>>,
        request: Self::Request,
    ) -> Result<Self::Response> {
        deployment.embedding(request).await
    }
}
