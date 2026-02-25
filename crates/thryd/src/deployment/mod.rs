use crate::model::Model;
use crate::UsageTracker;
use std::sync::Arc;

pub struct Deployment<M: Model> {
    model: Arc<M>,
    usage_tracker: Option<UsageTracker>,
}






