use handlebars::handlebars_helper;
use serde_json::Value;

handlebars_helper!(len: |v: Value| {
    if v.is_array(){
        v.as_array().unwrap().len()
    }else if v.is_object(){
        v.as_object().unwrap().len()
    }else if v.is_string(){
        v.as_str().unwrap().len()
    }else{
        0
    }
    
});