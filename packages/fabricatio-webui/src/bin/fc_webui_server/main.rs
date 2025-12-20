use axum::{response::Html, routing::get, Json, Router};
use serde::Serialize;
use std::net::SocketAddr;
use tower_http::{cors::CorsLayer, services::ServeDir};

async fn spa_handler() -> Html<&'static str> {
    // 从 Python 包内读取 index.html（需配合 PyO3）
    Html(std::include_str!(
        "../../../python/fabricatio_webui/www/index.html"
    ))
}
#[derive(Serialize)]
struct ApiResponse {
    message: String,
}
async fn hello_api() -> Json<ApiResponse> {
    Json(ApiResponse {
        message: "Hello from your Axum server!".to_string(),
    })
}

#[tokio::main]
async fn main() {
    let app: Router = Router::new()
        // API 路由
        .route("/api/hello", get(hello_api))
        // 静态资源
        .nest_service(
            "/assets",
            ServeDir::new("../../python/fabricatio_webui/www/assets"),
        )
        // SPA fallback
        .fallback(spa_handler)
        // CORS（开发时需要）
        .layer(CorsLayer::permissive());
    let addr = SocketAddr::from(([127, 0, 0, 1], 3000));
    let ls = tokio::net::TcpListener::bind(addr).await.unwrap();
    println!("Server running on http://{addr}");

    axum::serve(ls, app.into_make_service()).await.unwrap();
}
