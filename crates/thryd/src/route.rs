use crate::deployment::Deployment;
use crate::model::Model;
use crate::provider::Provider;
use crate::PersistentCache;
use std::sync::Arc;
use tokio::sync::Mutex;

struct Router<M: Model> {
    cache: PersistentCache,
    providers: Vec<Arc<dyn Provider>>,
    deployments: Vec<Arc<Mutex<Deployment<M>>>>,
}
