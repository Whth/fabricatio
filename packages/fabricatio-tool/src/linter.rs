use rustpython_ast::Expr;
use rustpython_ast::Stmt;
use rustpython_ast::Visitor;
use rustpython_ast::text_size::TextRange;
use rustpython_parser::{Mode, parse};
use std::collections::HashSet;

/// Configuration struct for the linter.
/// Holds sets of forbidden modules, imports, and function calls.
#[derive(Default)]
pub struct LinterConfig {
    forbidden_modules: Option<HashSet<String>>,
    forbidden_imports: Option<HashSet<String>>,
    forbidden_calls: Option<HashSet<String>>,
}

impl LinterConfig {
    /// Creates a new, empty LinterConfig with default values.
    pub fn new() -> Self {
        Self::default()
    }

    /// Adds forbidden modules to the configuration.
    pub fn with_forbidden_modules(mut self, modules: HashSet<String>) -> Self {
        self.forbidden_modules = Some(modules);
        self
    }

    /// Adds forbidden imports to the configuration.
    pub fn with_forbidden_imports(mut self, imports: HashSet<String>) -> Self {
        self.forbidden_imports = Some(imports);
        self
    }

    /// Adds forbidden function calls to the configuration.
    pub fn with_forbidden_calls(mut self, calls: HashSet<String>) -> Self {
        self.forbidden_calls = Some(calls);
        self
    }
}

struct LinterVisitor<'a> {
    config: &'a LinterConfig,
    violations: Vec<String>,
}

impl<'a> LinterVisitor<'a> {
    fn with(config: &'a LinterConfig) -> Self {
        Self {
            config,
            violations: vec![],
        }
    }
}

impl<'a> Visitor for LinterVisitor<'a> {
    fn visit_stmt(&mut self, node: Stmt<TextRange>) {
        // Check current statement for violations
        if let Some(violation) = node
            .as_import_stmt()
            .map(|stmt| check_import(&Stmt::Import(stmt.clone()), self.config))
        {
            if let Some(violation) = violation {
                self.violations.push(violation);
            }
        }

        if let Some(violation) = node
            .as_import_from_stmt()
            .map(|stmt| check_import(&Stmt::ImportFrom(stmt.clone()), self.config))
        {
            if let Some(violation) = violation {
                self.violations.push(violation);
            }
        }

        self.generic_visit_stmt(node)
    }

    fn visit_expr(&mut self, node: Expr<TextRange>) {
        if let Some(violation) = node
            .as_call_expr()
            .map(|expr| check_call(&Expr::Call(expr.clone()), self.config))
        {
            if let Some(violation) = violation {
                self.violations.push(violation);
            }
        }
        self.generic_visit_expr(node)
    }
}

/// Checks if an import statement uses any forbidden modules or names.
fn check_import(stmt: &Stmt, config: &LinterConfig) -> Option<String> {
    match stmt {
        Stmt::Import(a) => a
            .names
            .iter()
            .filter_map(|alias| {
                let module = &alias.name;
                is_forbidden_module(module, config)
                    .then(|| format!("Forbidden import module: {}", module))
            })
            .next(),
        Stmt::ImportFrom(a) => a
            .module
            .as_ref()
            .filter(|module_str| is_forbidden_module(module_str, config))
            .map(|module_str| format!("Forbidden import module: {}", module_str))
            .or_else(|| {
                a.names.iter().find_map(|alias| {
                    let name = alias.name.as_str();
                    config
                        .forbidden_imports
                        .as_ref()
                        .filter(|forbidden_imports| forbidden_imports.contains(&name.to_string()))
                        .map(|_| format!("Forbidden import: {}", name))
                })
            }),
        _ => None,
    }
}

/// Checks if a function call uses any forbidden function names.
fn check_call(expr: &Expr, config: &LinterConfig) -> Option<String> {
    if let Expr::Call(call) = expr {
        if let Some(name) = call.func.clone().name_expr() {
            let call_name = name.id.as_str();
            if config
                .forbidden_calls
                .as_ref()
                .map_or(false, |calls| calls.contains(&call_name.to_string()))
            {
                return Some(format!("Forbidden function call: {}()", call_name));
            }
        }
    }
    None
}

/// Helper function to determine if a module is forbidden.
fn is_forbidden_module(module: &str, config: &LinterConfig) -> bool {
    config
        .forbidden_modules
        .as_ref()
        .map_or(false, |modules| modules.contains(module))
        || ["os", "sys", "subprocess", "shutil"].contains(&module)
}

/// Gathers all violations found in the provided source code based on the given linter configuration.
///
/// This function parses the source code, traverses its abstract syntax tree (AST),
/// and identifies any forbidden patterns as defined by the linter configuration.
///
/// # Arguments
///
/// * source - A string-like input representing the source code to analyze.
/// * config - The linter configuration specifying forbidden modules, imports, and calls.
///
/// # Returns
///
/// A Result containing:
/// - A vector of strings listing all identified violations.
/// - An error message if parsing or traversal fails.
pub fn gather_violations<S: AsRef<str>>(
    source: S,
    config: LinterConfig,
) -> Result<Vec<String>, String> {
    let module = parse(source.as_ref(), Mode::Module, "<string>").map_err(|err| err.to_string())?;
    let mut vis = LinterVisitor::with(&config);

    // Traverse the module body and check each statement for violations
    module
        .as_module()
        .ok_or("No module found")?
        .body
        .iter()
        .for_each(|stmt| {
            vis.visit_stmt(stmt.clone());
            if let Some(expr) = stmt.as_expr_stmt() {
                vis.visit_expr(expr.value.as_ref().clone())
            }
        });

    Ok(vis.violations)
}
