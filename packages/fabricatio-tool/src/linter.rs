use rustpython_ast::text_size::TextRange;
use rustpython_ast::{Expr, Stmt, Visitor};
use rustpython_parser::{Mode, parse};
use std::collections::HashSet;

/// Configuration struct for defining allowlist/denylist rules
#[derive(Default)]
pub struct LinterConfig {
    module_mode: CheckMode,
    import_mode: CheckMode,
    call_mode: CheckMode,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CheckMode {
    Disabled,
    Whitelist(HashSet<String>),
    Blacklist(HashSet<String>),
}

impl Default for CheckMode {
    fn default() -> Self {
        CheckMode::Disabled
    }
}

impl LinterConfig {
    /// Creates a new LinterConfig with default settings
    pub fn new() -> Self {
        Self::default()
    }

    // --- Module-related configurations ---
    /// Sets allowed modules (whitelist mode)
    pub fn with_allowed_modules(mut self, modules: HashSet<String>) -> Self {
        self.module_mode = CheckMode::Whitelist(modules);
        self
    }

    /// Sets forbidden modules (blacklist mode)
    pub fn with_forbidden_modules(mut self, modules: HashSet<String>) -> Self {
        self.module_mode = CheckMode::Blacklist(modules);
        self
    }

    // --- Import-related configurations ---
    /// Sets allowed imports (whitelist mode)
    pub fn with_allowed_imports(mut self, imports: HashSet<String>) -> Self {
        self.import_mode = CheckMode::Whitelist(imports);
        self
    }

    /// Sets forbidden imports (blacklist mode)
    pub fn with_forbidden_imports(mut self, imports: HashSet<String>) -> Self {
        self.import_mode = CheckMode::Blacklist(imports);
        self
    }

    // --- Function call-related configurations ---
    /// Sets allowed function calls (whitelist mode)
    pub fn with_allowed_calls(mut self, calls: HashSet<String>) -> Self {
        self.call_mode = CheckMode::Whitelist(calls);
        self
    }

    /// Sets forbidden function calls (blacklist mode)
    pub fn with_forbidden_calls(mut self, calls: HashSet<String>) -> Self {
        self.call_mode = CheckMode::Blacklist(calls);
        self
    }
}

/// AST visitor for checking linting rules
struct LinterVisitor<'a> {
    config: &'a LinterConfig,
    violations: Vec<String>,
}

impl<'a> LinterVisitor<'a> {
    /// Creates a new visitor with the given configuration
    fn with(config: &'a LinterConfig) -> Self {
        Self {
            config,
            violations: vec![],
        }
    }
}

impl<'a> Visitor for LinterVisitor<'a> {
    /// Visits statements to check for violations
    fn visit_stmt(&mut self, node: Stmt<TextRange>) {
        if let Some(violation) = node
            .as_import_stmt()
            .map(|stmt| check_import(&Stmt::Import(stmt.clone()), self.config))
            .flatten()
        {
            self.violations.push(violation);
        }

        if let Some(violation) = node
            .as_import_from_stmt()
            .map(|stmt| check_import(&Stmt::ImportFrom(stmt.clone()), self.config))
            .flatten()
        {
            self.violations.push(violation);
        }

        self.generic_visit_stmt(node)
    }

    /// Visits expressions to check for violations
    fn visit_expr(&mut self, node: Expr<TextRange>) {
        if let Some(violation) = node
            .as_call_expr()
            .map(|expr| check_call(&Expr::Call(expr.clone()), self.config))
            .flatten()
        {
            self.violations.push(violation);
        }

        self.generic_visit_expr(node)
    }
}

/// Generic checker for allowlist/denylist modes
fn check_in_mode<T: ToString + AsRef<str>>(value: &T, mode: &CheckMode) -> Option<String> {
    const HARD_BLACKLISTED_MODULES: &[&str] = &["os", "sys", "subprocess", "shutil"];
    let val_str = value.to_string();

    // Hardcoded blacklist takes priority
    if HARD_BLACKLISTED_MODULES.contains(&value.as_ref()) {
        return Some(val_str);
    }

    match mode {
        CheckMode::Disabled => None,
        CheckMode::Blacklist(set) if set.contains(&val_str) => Some(val_str),
        CheckMode::Whitelist(set) if !set.contains(&val_str) => Some(val_str),
        _ => None,
    }
}

/// Checks import statements against configured rules
fn check_import(stmt: &Stmt, config: &LinterConfig) -> Option<String> {
    match stmt {
        Stmt::Import(a) => a.names.iter().find_map(|alias| {
            check_in_mode(&alias.name, &config.module_mode)
                .map(|m| format!("Forbidden import module: {}", m))
        }),
        Stmt::ImportFrom(a) => {
            if let Some(module_str) = &a.module {
                if let Some(msg) = check_in_mode(module_str, &config.module_mode)
                    .map(|m| format!("Forbidden import module: {}", m))
                {
                    return Some(msg);
                }
            }

            a.names.iter().find_map(|alias| {
                check_in_mode(&alias.name, &config.import_mode)
                    .map(|n| format!("Forbidden import: {}", n))
            })
        }
        _ => None,
    }
}

/// Checks function calls against configured rules
fn check_call(expr: &Expr, config: &LinterConfig) -> Option<String> {
    if let Expr::Call(call) = expr {
        if let Some(name) = call.func.clone().name_expr() {
            let call_name = name.id.as_str();
            return check_in_mode(&call_name, &config.call_mode)
                .map(|_| format!("Forbidden function call: {}()", call_name));
        }
    }
    None
}

/// Main function: analyzes source code and collects violations
pub fn gather_violations<S: AsRef<str>>(
    source: S,
    config: LinterConfig,
) -> Result<Vec<String>, String> {
    let module = parse(source.as_ref(), Mode::Module, "<string>").map_err(|err| err.to_string())?;
    let mut vis = LinterVisitor::with(&config);

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
