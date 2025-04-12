"""Fix the article."""

from fabricatio.models.extra.article_main import Article

a = Article.from_persistent(
    r"persistent\to_dump\Article_20250408_103051_51d822.json")
a.convert_tex()


from fabricatio.fs.curd import dump_text

dump_text("corrected.typ",a.finalized_dump())
