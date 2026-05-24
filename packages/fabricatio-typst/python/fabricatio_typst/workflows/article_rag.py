"""Store article essence in the database."""

from fabricatio_core import WorkFlow
from fabricatio_core.utils import cfg

cfg(["lancedb"])


from fabricatio_typst.actions.article import ExtractArticleEssence
from fabricatio_typst.actions.article_rag import StoreArticleEssence

StoreArticle = WorkFlow(
    name="Extract Article Essence",
    description="Extract the essence of an article in the given path, and store it in the database.",
    steps=(ExtractArticleEssence(output_key="documents"), StoreArticleEssence(output_key="task_output")),
)
