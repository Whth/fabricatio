//! The evaluation model backed by TypeSafe's Jev, over the System One evaluation API.

use std::sync::Arc;

use async_trait::async_trait;
use jevlin::Model as JevModelName;

use crate::JevProvider;
use crate::ModelName;
use crate::model::{EvaluationModel, EvaluationRequest, EvaluationResponse, Model};
use crate::provider::Provider;

/// A Jev model: one call evaluates a state against a set of typed questions.
///
/// The request carries the questions and, normally, the model that answers them. A request that
/// still holds the moving [`jev-latest`](jevlin::Model::LATEST_ALIAS) alias takes this deployment's
/// model name instead, so pinning the version in a deployment id — `typesafe/jev-1.13.0` — pins it
/// for every call that does not pin one itself, and a caller that pins a version keeps it.
///
/// The call itself is the provider's: it rides the connection shared for that endpoint, and its
/// retries belong to the router, like every other modality's.
pub struct JevModel {
    name: String,
    provider: Arc<JevProvider>,
}

impl JevModel {
    /// Pairs a model name with the provider that evaluates through it.
    pub fn new(name: ModelName, provider: Arc<JevProvider>) -> Self {
        Self { name, provider }
    }

    /// The request as this model will send it.
    ///
    /// The deployment decides which model answers when the caller left the alias in place; a model
    /// the caller pinned is the caller's to choose and travels unchanged.
    pub fn request_for(&self, mut request: EvaluationRequest) -> EvaluationRequest {
        if request.model.as_str() == JevModelName::LATEST_ALIAS {
            request.model = JevModelName::from(self.name.clone());
        }
        request
    }
}

impl Model for JevModel {
    fn model_name(&self) -> &str {
        &self.name
    }

    fn provider(&self) -> Arc<dyn Provider> {
        self.provider.clone()
    }
}

#[async_trait]
impl EvaluationModel for JevModel {
    async fn evaluate(&self, request: EvaluationRequest) -> crate::Result<EvaluationResponse> {
        self.provider.evaluate(&self.request_for(request)).await
    }
}

/// A canned evaluation response for this crate's tests: one yes/no answer, plus usage.
///
/// Kept here so the tests of the tag, the deployment and the dummy model all script the same wire
/// shape.
#[cfg(test)]
pub(crate) fn test_response(urgent: f64) -> EvaluationResponse {
    EvaluationResponse {
        model: JevModelName::from("jev-test"),
        answers: std::collections::BTreeMap::from([(
            "is_urgent".to_string(),
            crate::model::EvaluationAnswer::Noul(jevlin::NoulAnswer { noul: urgent }),
        )]),
        usage: jevlin::Usage {
            input_tokens: 12,
            output_tokens: 3,
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use jevlin::Question;
    use secrecy::SecretString;

    fn model(name: &str) -> JevModel {
        JevModel::new(
            name.to_string(),
            Arc::new(JevProvider::new("typesafe", SecretString::from("jev-test"))),
        )
    }

    fn request() -> EvaluationRequest {
        EvaluationRequest::new("The payouts have been failing for 3 days.")
            .with_question("is_urgent", Question::noul("Does this convey urgency?"))
    }

    #[test]
    fn an_unpinned_request_takes_the_deployments_model() {
        let resolved = model("jev-1.13.0").request_for(request());

        assert_eq!(resolved.model.as_str(), "jev-1.13.0");
    }

    #[test]
    fn a_pinned_request_keeps_the_model_it_named() {
        let resolved = model("jev-1.13.0").request_for(request().with_model("jev-1.12.0"));

        assert_eq!(resolved.model.as_str(), "jev-1.12.0");
    }

    #[test]
    fn the_state_and_questions_travel_unchanged() {
        let resolved = model("jev-1.13.0").request_for(request());

        assert_eq!(resolved.questions.len(), 1);
        assert_eq!(
            resolved.state,
            serde_json::json!("The payouts have been failing for 3 days.")
        );
    }
}
