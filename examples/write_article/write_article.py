"""Example of using the library."""

import asyncio
from pathlib import Path
from typing import List

from fabricatio import Event, Role, WorkFlow, logger
from fabricatio.actions.article import (
    GenerateArticleProposal,
    GenerateInitialOutline,
    LoadArticle,
)
from fabricatio.actions.article_rag import TweakArticleRAG, WriteArticleContentRAG
from fabricatio.actions.fs import ReadText
from fabricatio.actions.output import (
    DumpFinalizedOutput,
    GatherAsList,
    PersistentAll,
    RetrieveFromLatest,
    RetrieveFromPersistent,
)
from fabricatio.actions.rules import DraftRuleSet, GatherRuleset
from fabricatio.models.action import Action
from fabricatio.models.extra.article_main import Article
from fabricatio.models.extra.article_outline import ArticleOutline
from fabricatio.models.extra.article_proposal import ArticleProposal
from fabricatio.models.extra.rule import RuleSet
from fabricatio.models.task import Task
from fabricatio.utils import ok


class Connect(Action):
    """Connect the article with the article_outline and article_proposal."""

    output_key: str = "article"
    """Connect the article with the article_outline and article_proposal."""

    async def _execute(
        self,
        article_briefing: str,
        article_proposal: ArticleProposal,
        article_outline: ArticleOutline,
        article: Article,
        **cxt,
    ) -> Article:
        """Connect the article with the article_outline and article_proposal."""
        return article.update_ref(article_outline.update_ref(article_proposal.update_ref(article_briefing)))


async def main(article: bool, rule: bool = False, fintune: bool = False) -> None:
    """Main function."""
    Role(
        name="Undergraduate Researcher",
        description="Write an outline for an article in typst format.",
        llm_model="openai/qwen-max",
        llm_temperature=0.6,
        llm_stream=True,
        llm_top_p=0.53,
        llm_max_tokens=8191,
        llm_rpm=600,
        llm_tpm=900000,
        registry={
            Event.quick_instantiate(ns := "article"): WorkFlow(
                name="Generate Article Outline",
                description="Generate an outline for an article. dump the outline to the given path. in typst format.",
                steps=(
                    *RetrieveFromLatest.from_mapping(
                        retrieve_cls=RuleSet,
                        mapping={
                            "outline_ruleset": "persistent_ruleset/outline_ruleset",
                            "dep_ref_ruleset": "persistent_ruleset/dep_ref_ruleset",
                            "rev_dep_ref_ruleset": "persistent_ruleset/rev_dep_ref_ruleset",
                            "para_ruleset": "persistent_ruleset/para_ruleset",
                            "ref_ruleset": "persistent_ruleset/ref_ruleset",
                            "lang_ruleset": "persistent_ruleset/lang_ruleset",
                            "cite_ruleset": "persistent_ruleset/cite_ruleset",
                            "article_outline": "persistent/article_outline",
                        },
                    ),
                    RetrieveFromPersistent(
                        output_key="article_outline",
                        load_path=r"persistent/article_outline/ArticleOutline_20250407_203349_9c9353.json",
                        retrieve_cls=ArticleOutline,
                    ),
                    GenerateArticleProposal,
                    GenerateInitialOutline(output_key="article_outline", supervisor=False),
                    *GatherRuleset.from_mapping(
                        {
                            "intro_fix_ruleset": ["para_ruleset"],
                            "ref_fix_ruleset": ["ref_ruleset"],
                            "ref_twk_ruleset": ["dep_ref_ruleset", "ref_ruleset"],
                            "article_gen_ruleset": ["para_ruleset"],
                            "writing_ruleset": ["cite_ruleset"],
                        }
                    ),
                    WriteArticleContentRAG(
                        output_key="to_dump",
                        llm_top_p=0.46,
                        ref_limit=60,
                        llm_model="openai/qwq-plus",
                        target_collection="article_chunks",
                        extractor_model="openai/qwen-max",
                        query_model="openai/qwen-plus",
                    ),
                    DumpFinalizedOutput(output_key="task_output"),
                    PersistentAll,
                ),
            ).update_init_context(
                article_briefing=Path("./article_briefing.txt").read_text(),
                dump_path="out.typ",
                persist_dir="persistent",
                collection_name="article_chunks",
            ),
            Event.quick_instantiate(finetune := "article_finetune"): WorkFlow(
                name="Generate Article Outline",
                description="Generate an outline for an article. dump the outline to the given path. in typst format.",
                steps=(
                    *RetrieveFromLatest.from_mapping(
                        retrieve_cls=RuleSet,
                        mapping={
                            "outline_ruleset": "persistent_ruleset/outline_ruleset",
                            "dep_ref_ruleset": "persistent_ruleset/dep_ref_ruleset",
                            "rev_dep_ref_ruleset": "persistent_ruleset/rev_dep_ref_ruleset",
                            "para_ruleset": "persistent_ruleset/para_ruleset",
                            "ref_ruleset": "persistent_ruleset/ref_ruleset",
                            "lang_ruleset": "persistent_ruleset/lang_ruleset",
                            "cite_ruleset": "persistent_ruleset/cite_ruleset",
                            "article_proposal": "persistent/article_proposal",
                            "article_outline": "persistent/article_outline",
                            "article": "persistent/article",
                        },
                    ),
                    ReadText(read_path="out.typ"),
                    LoadArticle,
                    Connect,
                    *GatherRuleset.from_mapping(
                        {
                            "intro_fix_ruleset": ["para_ruleset"],
                            "ref_fix_ruleset": ["ref_ruleset"],
                            "article_gen_ruleset": ["para_ruleset"],
                            "twk_rag_ruleset": ["para_ruleset", "cite_ruleset"],
                        }
                    ),
                    TweakArticleRAG(
                        output_key="to_dump",
                    ),
                    DumpFinalizedOutput(output_key="task_output"),
                    PersistentAll,
                ),
            ).update_init_context(
                article_briefing=Path("./article_briefing.txt").read_text(),
                dump_path="out_fix.typ",
                persist_dir="persistent_fix",
                collection_name="article_essence_0324",
            ),
            Event.quick_instantiate(rule_ns := "rule"): WorkFlow(
                name="Generate Draft Rule Set",
                description="Generate a draft rule set for the article.",
                llm_model="openai/deepseek-v3-250324",
                llm_stream=False,
                steps=(
                    *DraftRuleSet.from_mapping(
                        {
                            "para_ruleset": (
                                1,
                                "如果`paragraphs`字段为空列表，那么你就需要按照`expected_word_count`来为章节补充内容",
                            ),
                            "cite_ruleset": (
                                1,
                                "1. 参考文献引用格式：(作者等, 年份)#cite(<bibtex_key>)\n2. #cite()必须用尖括号包裹单个BibTeX键，多引用需重复使用",
                            ),
                            "lang_ruleset": (
                                1,
                                "1. 所有标题和正文内容必须使用中文,如果不为中文你需要翻译过来\n2. 术语和专业词汇需使用中文表述,英文缩写第一次出现的时候需要在其后面‘()’来辅助说明",
                            ),
                            "dep_ref_ruleset": (1, "章节的`depend_on`字段的`ArticleRef`只能引用当前章节之前的元素。\n"),
                            "rev_dep_ref_ruleset": (
                                1,
                                "章节的`support_to`字段的`ArticleRef`只能引用当前章节之后的元素。\n",
                            ),
                            "ref_ruleset": (1, "ArticleRef必须指向已定义元素"),
                            "outline_ruleset": (1, "标题使用学术术语"),
                        }
                    ),
                    GatherAsList(gather_suffix="ruleset").to_task_output(),
                    PersistentAll(persist_dir="persistent_ruleset"),
                ),
            ),
        },
    )

    if rule:
        draft_rule_task: Task[List[RuleSet]] = Task(name="draft a rule set")
        rule_set = ok(await draft_rule_task.delegate(rule_ns), "Failed to generate ruleset")
        logger.success(f"Ruleset:\n{len(rule_set)}")
    if article:
        proposed_task = Task(name="write an article")
        path = ok(await proposed_task.delegate(ns), "Failed to generate an article ")
        logger.success(f"The outline is saved in:\n{path}")
    if fintune:
        proposed_task = Task(name="finetune an article")
        path = ok(await proposed_task.delegate(finetune), "Failed to generate an article")
        logger.success(f"The outline is saved in:\n{path}")


if __name__ == "__main__":
    asyncio.run(main(True, False, False))
