use rustpython_parser::{Mode, parse};
use rustpython_ast::Stmt;
use rustpython_ast::Expr;
use rustpython_ast::Mod;

use std::collections::HashSet;

#[derive(Default)]
pub struct LinterConfig {
    forbidden_modules: Option<HashSet<&'static str>>,
    forbidden_imports: Option<HashSet<&'static str>>,
    forbidden_calls: Option<HashSet<&'static str>>,
}

impl LinterConfig {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_forbidden_modules(mut self, modules: HashSet<&'static str>) -> Self {
        self.forbidden_modules = Some(modules);
        self
    }

    pub fn with_forbidden_imports(mut self, imports: HashSet<&'static str>) -> Self {
        self.forbidden_imports = Some(imports);
        self
    }

    pub fn with_forbidden_calls(mut self, calls: HashSet<&'static str>) -> Self {
        self.forbidden_calls = Some(calls);
        self
    }
}

fn check_import(stmt: &Stmt, config: &LinterConfig) -> Option<String> {
    match stmt {
        Stmt::Import(a) => a.names.iter()
            .filter_map(|alias| {
                let module = &alias.name;
                is_forbidden_module(module, config)
                    .then(|| format!("禁止导入模块: {}", module))
            })
            .next(),
        Stmt::ImportFrom(a) => a.module.as_ref()
            .filter(|&module_str| is_forbidden_module(module_str, config))
            .map(|module_str| format!("禁止导入模块: {}", module_str))
            .or_else(|| a.names.iter().find_map(|alias| {
                let name = alias.name.as_str();
                config.forbidden_imports.as_ref()
                    .filter(|forbidden_imports| forbidden_imports.contains(name))
                    .map(|_| format!("禁止导入: {}", name))
            })),
        _ => None,
    }
}

fn check_call(expr: &Expr, config: &LinterConfig) -> Option<String> {
    if let Expr::Call(call) = expr {
        if let Some(name) = call.func.clone().name_expr() {
            let call_name = name.id.as_str();
            if config.forbidden_calls.as_ref()
                .map_or(false, |calls| calls.contains(&call_name))
            {
                return Some(format!("禁止调用: {}()", call_name));
            }
        }
    }
    None
}

fn is_forbidden_module(module: &str, config: &LinterConfig) -> bool {
    config.forbidden_modules.as_ref()
        .map_or(false, |modules| modules.contains(module))
        || ["os", "sys", "subprocess", "shutil"].contains(&module)
}

pub fn lint_code_with_config(source: &str, config: Option<LinterConfig>) -> Result<(), Vec<String>> {
    let config = config.unwrap_or_default();

    let ast_result = parse(source, Mode::Module, "dummy.py");

    let errors: Vec<String> = match ast_result {
        Ok(Mod::Module(m)) => m.body.iter()
            .filter_map(|stmt| {
                check_import(stmt, &config).or_else(|| {
                    if let Stmt::Expr(exp) = stmt {
                        check_call(&exp.value, &config)
                    } else {
                        None
                    }
                })
            })
            .collect(),
        Err(e) => vec![format!("语法解析失败: {:?}", e)],
        _ => vec![],
    };

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}