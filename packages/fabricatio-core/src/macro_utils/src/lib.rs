use proc_macro::TokenStream;
use quote::quote;
use syn::{parse_macro_input, Data, DeriveInput, Error, Fields, Ident};

#[proc_macro_derive(TemplateDefault, attributes(suffix))]
pub fn derive_template_default(input: TokenStream) -> TokenStream {
    let input = parse_macro_input!(input as DeriveInput);
    let struct_name = &input.ident;

    let data = if let Data::Struct(data) = &input.data {
        data
    } else {
        return Error::new_spanned(input, "Only structs are supported") // Changed from `input.data` to `input`
            .into_compile_error()
            .into();
    };

    let fields = if let Fields::Named(fields) = &data.fields {
        &fields.named
    } else {
        return Error::new_spanned(input, "Only named fields are supported") // Changed from `data` to `input`
            .into_compile_error()
            .into();
    };

    // Process fields and collect names
    let mut field_names = Vec::new();
    for field in fields {
        let ident = if let Some(ref ident) = field.ident {
            ident
        } else {
            continue;
        };

        let name_str = ident.to_string();
        if !name_str.ends_with("_template") {
            return Error::new_spanned(ident, "All fields must end with '_template'")
                .into_compile_error()
                .into();
        }

        let new_name = name_str.strip_suffix("_template").unwrap().to_string();
        field_names.push((ident.clone(), new_name));
    }

    // Generate field initializers
    let (idents, defaults): (Vec<Ident>, Vec<String>) = field_names
        .into_iter()
        .unzip();

    // Create the expanded implementation
    let expanded = quote! {
        impl Default for #struct_name {
            fn default() -> Self {
                Self {
                    #(
                        #idents: String::from(#defaults),
                    )*
                }
            }
        }
    };

    TokenStream::from(expanded)
}