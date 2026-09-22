//! Derive macro for [`jevlin`](https://docs.rs/jevlin) question sets.
//!
//! Use `jevlin::Answers` rather than depending on this crate directly: the re-export carries the
//! documentation, and this crate only implements it.

use proc_macro::TokenStream;
use proc_macro2::TokenStream as TokenStream2;
use quote::quote;
use syn::punctuated::Punctuated;
use syn::spanned::Spanned;
use syn::{Data, DeriveInput, Fields, Meta, Token, parse_macro_input};

mod jev;

use jev::{JevAttribute, Kind};

/// Turns a struct with named fields into a typed System One question set.
///
/// Each field is one question, declared with a `#[jev(kind, instructions, …)]` attribute; the field
/// name is the question id, and the field type is the answer the question comes back as. The derive
/// generates:
///
/// - `impl jevlin::QuestionSet for YourStruct`, carrying the ids and the request builder, so
///   `jevlin::SystemOne::ask::<YourStruct>(state)` can run it and `jevlin::Response::read::<YourStruct>()`
///   can read it;
/// - an inherent `YourStruct::request(state)` and `YourStruct::IDS`, usable without importing the
///   trait;
/// - a build failure for anything the API would reject: an unknown question kind, an answer type
///   that does not match its question, a `choice` without options or with more than 255, a `score`
///   with fewer than 2 or more than 10 levels.
///
/// The struct also needs `serde::Deserialize` (or `jevlin::Deserialize`), because reading a response
/// goes through serde. A `#[serde(rename = "…")]` on a field renames the question id with it, and a
/// struct-level `#[serde(rename_all = "…")]` is rejected rather than silently moving the keys.
///
/// ```rust,ignore
/// use jevlin::{Answers, ChoiceAnswer, Deserialize, NoulAnswer, ScoreAnswer};
///
/// #[derive(Answers, Deserialize)]
/// struct Triage {
///     #[jev(noul, "Does this convey urgency?", yes = "Time-critical", no = "No urgency")]
///     is_urgent: NoulAnswer,
///
///     #[jev(choice, "Which team should handle this?",
///           billing = "Payments, invoicing, refunds",
///           technical = "Bugs, outages, integrations")]
///     department: ChoiceAnswer,
///
///     #[jev(score, "How frustrated is the customer?", "Calm", "Frustrated", "Very angry")]
///     frustration: ScoreAnswer,
/// }
///
/// let outcome = client.ask::<Triage>("Help! My payouts have been failing for 3 days.").await?;
/// println!("{} {}", outcome.answers.is_urgent, outcome.usage.input_tokens);
/// ```
#[proc_macro_derive(Answers, attributes(jev))]
pub fn derive_answers(input: TokenStream) -> TokenStream {
    let input = parse_macro_input!(input as DeriveInput);
    match answers(&input) {
        Ok(generated) => generated.into(),
        Err(error) => error.into_compile_error().into(),
    }
}

/// The pure half of the derive, so every diagnostic is testable without a compile cycle.
fn answers(input: &DeriveInput) -> syn::Result<TokenStream2> {
    let name = &input.ident;
    reject_rename_all(input)?;

    let fields = named_fields(input)?;
    if fields.is_empty() {
        return Err(syn::Error::new(
            input.span(),
            "a question set needs at least one question",
        ));
    }

    let mut ids = Vec::with_capacity(fields.len());
    let mut questions = Vec::with_capacity(fields.len());
    for field in fields {
        let attribute = field_attribute(field)?;
        check_field_type(field, attribute.kind())?;
        ids.push(question_id(field)?);
        questions.push(attribute.question()?);
    }

    Ok(quote! {
        #[automatically_derived]
        impl #name {
            /// The question ids this set asks, in declaration order.
            pub const IDS: &'static [&'static str] = &[#(#ids),*];

            /// Builds the request that asks these questions about `state`.
            pub fn request(state: impl ::core::convert::Into<::jevlin::State>) -> ::jevlin::Request {
                <Self as ::jevlin::QuestionSet>::request(::core::convert::Into::into(state))
            }
        }

        #[automatically_derived]
        impl ::jevlin::QuestionSet for #name {
            const IDS: &'static [&'static str] = &[#(#ids),*];

            fn request(state: ::jevlin::State) -> ::jevlin::Request {
                ::jevlin::Request::new(state)
                    #(.with_question(#ids, #questions))*
            }
        }
    })
}

/// The named fields of the struct, or a diagnostic saying why there are none.
fn named_fields(input: &DeriveInput) -> syn::Result<&Punctuated<syn::Field, Token![,]>> {
    if !input.generics.params.is_empty() {
        return Err(syn::Error::new(
            input.generics.span(),
            "a question set cannot be generic: its questions are declared here, not by a caller",
        ));
    }
    match &input.data {
        Data::Struct(data) => match &data.fields {
            Fields::Named(named) => Ok(&named.named),
            _ => Err(syn::Error::new(
                data.fields.span(),
                "a question set needs named fields: each field is one question",
            )),
        },
        Data::Enum(data) => Err(syn::Error::new(
            data.enum_token.span(),
            "`Answers` can only be derived for a struct with named fields",
        )),
        Data::Union(data) => Err(syn::Error::new(
            data.union_token.span(),
            "`Answers` can only be derived for a struct with named fields",
        )),
    }
}

/// The field's one `#[jev(...)]` attribute.
fn field_attribute(field: &syn::Field) -> syn::Result<JevAttribute> {
    let mut attribute = None;
    for item in &field.attrs {
        if !item.path().is_ident("jev") {
            continue;
        }
        if attribute.is_some() {
            return Err(syn::Error::new(
                item.span(),
                "a field carries one `#[jev(...)]` attribute",
            ));
        }
        attribute = Some(item.parse_args::<JevAttribute>()?);
    }
    attribute.ok_or_else(|| {
        syn::Error::new(
            field.span(),
            "a question field needs a `#[jev(noul | choice | score, \"…\")]` attribute",
        )
    })
}

/// Rejects a field whose type cannot hold the answer its question comes back as.
fn check_field_type(field: &syn::Field, kind: Kind) -> syn::Result<()> {
    let expected = kind.answer_type();
    let syn::Type::Path(path) = &field.ty else {
        return Err(syn::Error::new(
            field.ty.span(),
            format!(
                "a `{}` question needs a field of type `{expected}`",
                kind.name()
            ),
        ));
    };
    let Some(segment) = path.path.segments.last() else {
        return Err(syn::Error::new(
            path.span(),
            format!(
                "a `{}` question needs a field of type `{expected}`",
                kind.name()
            ),
        ));
    };
    if segment.ident == expected {
        return Ok(());
    }
    Err(syn::Error::new(
        segment.ident.span(),
        format!(
            "a `{}` question is answered with `{expected}`, so this field has that type, not `{}`",
            kind.name(),
            segment.ident
        ),
    ))
}

/// The id a question is filed under: the field's name, or the name its `#[serde(rename = "…")]` gives.
fn question_id(field: &syn::Field) -> syn::Result<String> {
    if let Some(renamed) = serde_rename(field)? {
        return Ok(renamed);
    }
    let Some(ident) = &field.ident else {
        return Err(syn::Error::new(
            field.span(),
            "a question field needs a name",
        ));
    };
    Ok(jev::ident_name(ident))
}

/// The field's own `#[serde(rename = "…")]`, so the question id and the serde key cannot drift.
fn serde_rename(field: &syn::Field) -> syn::Result<Option<String>> {
    for attribute in &field.attrs {
        if !attribute.path().is_ident("serde") {
            continue;
        }
        for meta in serde_metas(attribute)? {
            let Meta::NameValue(pair) = &meta else {
                continue;
            };
            if !pair.path.is_ident("rename") {
                continue;
            }
            let syn::Expr::Lit(syn::ExprLit {
                lit: syn::Lit::Str(rename),
                ..
            }) = &pair.value
            else {
                continue;
            };
            return Ok(Some(rename.value()));
        }
    }
    Ok(None)
}

/// Rejects a struct-level `#[serde(rename_all = "…")]`, which would move the serde keys off the ids.
fn reject_rename_all(input: &DeriveInput) -> syn::Result<()> {
    for attribute in &input.attrs {
        if !attribute.path().is_ident("serde") {
            continue;
        }
        for meta in serde_metas(attribute)? {
            if meta.path().is_ident("rename_all") {
                return Err(syn::Error::new(
                    meta.span(),
                    "`rename_all` is not supported: question ids come from the field names, so rename a single field with its own `#[serde(rename = \"…\")]`",
                ));
            }
        }
    }
    Ok(())
}

/// The nested metas of a `#[serde(...)]` attribute, if it is a list.
fn serde_metas(attribute: &syn::Attribute) -> syn::Result<Punctuated<Meta, Token![,]>> {
    match &attribute.meta {
        Meta::List(list) => list.parse_args_with(Punctuated::<Meta, Token![,]>::parse_terminated),
        _ => Ok(Punctuated::new()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn derive(source: &str) -> syn::Result<TokenStream2> {
        answers(&syn::parse_str::<DeriveInput>(source).unwrap())
    }

    fn field(source: &str) -> syn::Field {
        syn::parse_str::<syn::ItemStruct>(source)
            .unwrap()
            .fields
            .into_iter()
            .next()
            .unwrap()
    }

    #[test]
    fn rejects_a_field_without_a_question() {
        let error = derive("struct Wrong { urgency: NoulAnswer }").unwrap_err();

        assert!(
            error.to_string().contains("question field needs"),
            "got {error}"
        );
    }

    #[test]
    fn rejects_two_question_attributes_on_one_field() {
        let error = derive(
            r#"struct Wrong {
                #[jev(noul, "Is it urgent?")]
                #[jev(score, "How urgent?", "Low", "High")]
                urgency: NoulAnswer,
            }"#,
        )
        .unwrap_err();

        assert!(
            error.to_string().contains("one `#[jev(...)]`"),
            "got {error}"
        );
    }

    #[test]
    fn rejects_an_answer_type_that_does_not_match_its_question() {
        let error = derive(
            r#"struct Wrong {
                #[jev(noul, "Is it urgent?")]
                urgency: ChoiceAnswer,
            }"#,
        )
        .unwrap_err();

        assert!(error.to_string().contains("NoulAnswer"), "got {error}");
        assert!(error.to_string().contains("ChoiceAnswer"), "got {error}");
    }

    #[test]
    fn rejects_a_wrapped_answer_type() {
        let error = derive(
            r#"struct Wrong {
                #[jev(noul, "Is it urgent?")]
                urgency: Option<NoulAnswer>,
            }"#,
        )
        .unwrap_err();

        assert!(error.to_string().contains("NoulAnswer"), "got {error}");
    }

    #[test]
    fn rejects_an_empty_question_set() {
        let error = derive("struct Wrong {}").unwrap_err();

        assert!(
            error.to_string().contains("at least one question"),
            "got {error}"
        );
    }

    #[test]
    fn rejects_a_tuple_struct() {
        let error = derive("struct Wrong(NoulAnswer);").unwrap_err();

        assert!(error.to_string().contains("named fields"), "got {error}");
    }

    #[test]
    fn rejects_an_enum_or_a_union() {
        let enum_error = derive("enum Wrong { Urgent }").unwrap_err();
        assert!(
            enum_error.to_string().contains("struct with named fields"),
            "got {enum_error}"
        );

        let union_error = derive("union Wrong { urgency: u64 }").unwrap_err();
        assert!(
            union_error.to_string().contains("struct with named fields"),
            "got {union_error}"
        );
    }

    #[test]
    fn rejects_a_generic_question_set() {
        let error = derive(
            r#"struct Wrong<T> {
                #[jev(noul, "Is it urgent?")]
                urgency: T,
            }"#,
        )
        .unwrap_err();

        assert!(
            error.to_string().contains("cannot be generic"),
            "got {error}"
        );
    }

    #[test]
    fn rejects_rename_all() {
        let error = derive(
            r#"#[serde(rename_all = "camelCase")]
            struct Wrong {
                #[jev(noul, "Is it urgent?")]
                urgency: NoulAnswer,
            }"#,
        )
        .unwrap_err();

        assert!(error.to_string().contains("rename_all"), "got {error}");
    }

    #[test]
    fn takes_the_question_id_from_the_field_name() {
        let plain = field(r#"struct S { #[jev(noul, "Is it urgent?")] urgency: NoulAnswer }"#);
        assert_eq!(question_id(&plain).unwrap(), "urgency");

        let raw = field(r#"struct S { #[jev(noul, "Is it so?")] r#type: NoulAnswer }"#);
        assert_eq!(question_id(&raw).unwrap(), "type");
    }

    #[test]
    fn a_serde_rename_moves_the_question_id_with_it() {
        let renamed = field(
            r#"struct S {
                #[serde(rename = "team-2")]
                #[jev(choice, "Which team?", billing = "Payments")]
                team: ChoiceAnswer,
            }"#,
        );

        assert_eq!(question_id(&renamed).unwrap(), "team-2");
    }

    #[test]
    fn a_serde_attribute_without_a_rename_is_ignored() {
        let field = field(
            r#"struct S {
                #[serde(default, skip_serializing_if = "Option::is_none")]
                #[jev(noul, "Is it urgent?")]
                urgency: NoulAnswer,
            }"#,
        );

        assert_eq!(question_id(&field).unwrap(), "urgency");
    }

    #[test]
    fn accepts_a_well_formed_question_set() {
        let generated = derive(
            r#"#[derive(Answers)]
            struct Triage {
                #[jev(noul, "Does this convey urgency?", yes = "Time-critical", no = "No urgency")]
                is_urgent: NoulAnswer,

                #[jev(choice, "Which team should handle this?",
                      billing = "Payments, invoicing, refunds",
                      technical = "Bugs, outages, integrations")]
                department: ChoiceAnswer,

                #[jev(score, "How frustrated is the customer?", "Calm", "Frustrated", "Very angry")]
                frustration: ScoreAnswer,
            }"#,
        )
        .unwrap();

        let generated = generated.to_string();
        assert!(generated.contains("QuestionSet"), "got {generated}");
        assert!(
            generated.contains("\"is_urgent\"") && generated.contains("\"department\""),
            "every declared question is filed under its field name: {generated}"
        );
    }
}
