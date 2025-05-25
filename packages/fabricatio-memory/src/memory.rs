use chrono::Utc;
use nucleo_matcher::pattern::{AtomKind, CaseMatching, Normalization, Pattern};
use nucleo_matcher::{Config, Matcher, Utf32Str};
use polars::prelude::*;
use pyo3::prelude::*;
use std::cmp::Ordering;

#[pyclass]
#[derive(Debug, Clone)]
pub struct MemorySystem {
    storage: DataFrame,
}


#[pymethods]
impl MemorySystem {
    #[new]
    pub fn new() -> Self {
        let schema = Schema::from_iter(vec![
            Field::new("id".into(), DataType::UInt64),
            Field::new("timestamp".into(), DataType::Int64),
            Field::new("content".into(), DataType::String),
            Field::new("importance".into(), DataType::Float32),
            Field::new("last_accessed".into(), DataType::Int64),
            Field::new("access_count".into(), DataType::UInt32),
            Field::new("decay_rate".into(), DataType::Float32),
        ]);

        let df = DataFrame::empty_with_schema(&schema);
        MemorySystem { storage: df }
    }

    // 添加一条记忆
    pub fn remember(&mut self, id: u64, content: &str, importance: f32) {
        let now = Utc::now().timestamp();
        let id_col = UInt64Chunked::from_slice("id".into(), &[id]);
        let ts_col = Int64Chunked::from_slice("timestamp".into(), &[now]);
        let content_col = StringChunked::from_slice("content".into(), &[content]);
        let imp_col = Float32Chunked::from_slice("importance".into(), &[importance]);
        let lac_col = Int64Chunked::from_slice("last_accessed".into(), &[now]);
        let ac_col = UInt32Chunked::from_slice("access_count".into(), &[0]);
        let dr_col = Float32Chunked::from_slice("decay_rate".into(), &[0.95]);
        let df = DataFrame::new(vec![
            id_col.into_column(),
            ts_col.into_column(),
            content_col.into_column(),
            imp_col.into_column(),
            lac_col.into_column(),
            ac_col.into_column(),
            dr_col.into_column(),
        ]).unwrap();

        let concatenated = concat(&[self.storage.clone().lazy(), df.lazy()],
                                  UnionArgs::default()).unwrap().collect().unwrap();
        self.storage = concatenated;
    }

    // 输入门：判断是否要记住新内容
    pub fn input_gate(&self, new_content: &str, current_context: &str) -> bool {
        let similarity = semantic_similarity(new_content, current_context);
        println!("Input gate similarity: {}", similarity);
        similarity > 0.7
    }

    // 输出门：根据当前上下文召回最相关的记忆
    pub fn output_gate(&self, context: &str, top_k: usize) -> Vec<String> {
        if self.storage.height() == 0 {
            return vec![];
        }


        let contents = self.storage.column("content").unwrap();
        let importance = self.storage.column("importance").unwrap().f32().unwrap();
        let mut scores = Vec::new();

        for i in 0..contents.len() {
            if let Ok(content) = contents.get(i) {
                let score = semantic_similarity(context, content.to_string().as_str())
                    * importance.get(i).unwrap_or(0.5) as f32;
                scores.push((score, content.to_string()));
            }
        }

        scores.sort_by(|a, b| {
            b.0.partial_cmp(&a.0).unwrap_or(Ordering::Equal)
        });

        scores.into_iter().take(top_k).map(|(_, c)| c).collect()
    }

    // 遗忘门：定期清理低价值记忆
    pub fn forget_gate(&mut self) {
        let now = Utc::now().timestamp();
        let filtered = self.storage.clone().lazy()
            .filter(
                (col("importance") *
                    lit(0.95f32).pow((lit(now) - col("timestamp")) / lit(3600)))
                    .gt(lit(0.2f32))
            )
            .collect()
            .unwrap();

        self.storage = filtered;
    }

    // 获取所有记忆条目（调试用）
    pub fn get_all_memories(&self) -> Vec<String> {
        self.storage.column("content")
            .expect("Failed to get memory contents")
            .str()
            .expect("Failed to convert memory contents to strings")
            .into_iter()
            .map(|s| s.expect("Failed to convert memory content to string").into())
            .collect()
    }
}

// 使用 nucleo-matcher 实现的语义相似度函数
fn semantic_similarity(a: &str, b: &str) -> f32 {
    if a.is_empty() || b.is_empty() {
        return 0.0;
    }

    let mut matcher = Matcher::new(Config::DEFAULT);
    let pattern = Pattern::new(
        a,
        CaseMatching::Ignore,
        Normalization::Never,
        AtomKind::Fuzzy,
    );

    let mut buf = vec![];
    let score = pattern.score(Utf32Str::new(b, &mut buf), &mut matcher);

    match score {
        Some(s) => {
            let normalized = s as f32;
            println!("Raw nucleo score: {}, Normalized score: {}", s, normalized);
            normalized
        }
        None => 0.0,
    }
}


pub(crate) fn register(_: Python, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<MemorySystem>()?;
    Ok(())
}