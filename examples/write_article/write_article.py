"""Example of using the library."""

import asyncio
from pathlib import Path
from typing import List

from fabricatio import Event, Role, WorkFlow, logger
from fabricatio.actions.article import (
    FixIntrospectedErrors,
    GenerateArticle,
    GenerateArticleProposal,
    GenerateInitialOutline,
)
from fabricatio.actions.article_rag import TweakArticleRAG
from fabricatio.actions.output import DumpFinalizedOutput, GatherAsList, PersistentAll, RetrieveFromLatest
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
        llm_model="openai/deepseek-v3-250324",
        llm_temperature=1.3,
        llm_top_p=1.0,
        llm_max_tokens=8191,
        llm_rpm=1000,
        llm_tpm=5000000,
        registry={
            Event.quick_instantiate(ns := "article"): WorkFlow(
                name="Generate Article Outline",
                description="Generate an outline for an article. dump the outline to the given path. in typst format.",
                steps=(
                    RetrieveFromLatest(
                        retrieve_cls=RuleSet,
                        load_path="persistent_ruleset/outline_ruleset",
                        output_key="outline_ruleset",
                    ),
                    RetrieveFromLatest(
                        retrieve_cls=RuleSet,
                        load_path="persistent_ruleset/dep_ref_ruleset",
                        output_key="dep_ref_ruleset",
                    ),
                    RetrieveFromLatest(
                        retrieve_cls=RuleSet,
                        load_path="persistent_ruleset/rev_dep_ref_ruleset",
                        output_key="rev_dep_ref_ruleset",
                    ),
                    RetrieveFromLatest(
                        retrieve_cls=RuleSet, load_path="persistent_ruleset/cite_ruleset", output_key="cite_ruleset"
                    ),
                    RetrieveFromLatest(
                        retrieve_cls=RuleSet, load_path="persistent_ruleset/para_ruleset", output_key="para_ruleset"
                    ),
                    RetrieveFromLatest(
                        retrieve_cls=RuleSet, load_path="persistent_ruleset/ref_ruleset", output_key="ref_ruleset"
                    ),
                    RetrieveFromLatest(
                        retrieve_cls=RuleSet, load_path="persistent_ruleset/lang_ruleset", output_key="lang_ruleset"
                    ),
                    GenerateArticleProposal(llm_temperature=1.3),
                    GenerateInitialOutline(
                        output_key="article_outline",
                    ),
                    GatherRuleset(output_key="intro_fix_ruleset", to_gather=["para_ruleset"]),
                    FixIntrospectedErrors(
                        output_key="article_outline",
                    ),
                    PersistentAll,
                    GatherRuleset(output_key="ref_fix_ruleset", to_gather=["ref_ruleset"]),
                    GatherRuleset(output_key="ref_twk_ruleset", to_gather=["dep_ref_ruleset", "ref_ruleset"]),
                    GatherRuleset(output_key="article_gen_ruleset", to_gather=["para_ruleset"]),
                    GenerateArticle(
                        output_key="article",
                    ),
                    PersistentAll,
                    GatherRuleset(
                        output_key="twk_rag_ruleset", to_gather=["para_ruleset", "cite_ruleset", "lang_ruleset"]
                    ),
                    TweakArticleRAG(output_key="to_dump"),
                    DumpFinalizedOutput(output_key="task_output"),
                    PersistentAll,
                ),
            ).update_init_context(
                article_briefing=Path("./article_briefing.txt").read_text(),
                dump_path="out.typ",
                persist_dir="persistent",
                collection_name="article_essence_0324",
            ),
            Event.quick_instantiate(finetune := "article_finetune"): WorkFlow(
                name="Generate Article Outline",
                description="Generate an outline for an article. dump the outline to the given path. in typst format.",
                steps=(
                    RetrieveFromLatest(
                        retrieve_cls=RuleSet,
                        load_path="persistent_ruleset/outline_ruleset",
                        output_key="outline_ruleset",
                    ),
                    RetrieveFromLatest(
                        retrieve_cls=RuleSet,
                        load_path="persistent_ruleset/dep_ref_ruleset",
                        output_key="dep_ref_ruleset",
                    ),
                    RetrieveFromLatest(
                        retrieve_cls=RuleSet,
                        load_path="persistent_ruleset/rev_dep_ref_ruleset",
                        output_key="rev_dep_ref_ruleset",
                    ),
                    RetrieveFromLatest(
                        retrieve_cls=RuleSet, load_path="persistent_ruleset/cite_ruleset", output_key="cite_ruleset"
                    ),
                    RetrieveFromLatest(
                        retrieve_cls=RuleSet, load_path="persistent_ruleset/para_ruleset", output_key="para_ruleset"
                    ),
                    RetrieveFromLatest(
                        retrieve_cls=RuleSet, load_path="persistent_ruleset/ref_ruleset", output_key="ref_ruleset"
                    ),
                    RetrieveFromLatest(
                        retrieve_cls=ArticleProposal,
                        load_path="persistent/article_proposal",
                        output_key="article_proposal",
                    ),
                    RetrieveFromLatest(
                        retrieve_cls=ArticleOutline,
                        load_path="persistent/article_outline",
                        output_key="article_outline",
                    ),
                    RetrieveFromLatest(retrieve_cls=Article, load_path="persistent/article", output_key="article"),
                    Connect,
                    GatherRuleset(output_key="intro_fix_ruleset", to_gather=["para_ruleset"]),
                    GatherRuleset(output_key="ref_fix_ruleset", to_gather=["ref_ruleset"]),
                    GatherRuleset(output_key="article_gen_ruleset", to_gather=["para_ruleset"]),
                    GatherRuleset(output_key="twk_rag_ruleset", to_gather=["para_ruleset", "cite_ruleset"]),
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
                    # 精简后的para_ruleset规则
                    DraftRuleSet(
                        ruleset_requirement="如果`paragraphs`字段为空列表，那么你就需要按照`expected_word_count`来为章节补充内容",
                        output_key="para_ruleset",
                        rule_count=1,
                    ),
                    # 精简后的cite_ruleset规则
                    DraftRuleSet(
                        ruleset_requirement="1. 参考文献引用格式：(作者等, 年份)#cite(<bibtex_key>)\n"
                        "2. #cite()必须用尖括号包裹单个BibTeX键，多引用需重复使用",
                        output_key="cite_ruleset",
                        rule_count=1,
                    ),
                    # 新增中文检测规则集
                    DraftRuleSet(
                        ruleset_requirement="1. 所有标题和正文内容必须使用中文,如果不为中文你需要翻译过来\n"
                        "2. 术语和专业词汇需使用中文表述,英文缩写第一次出现的时候需要在其后面‘()’来辅助说明",
                        output_key="lang_ruleset",
                        rule_count=1,
                    ),
                    # 其他规则集保持原有结构但简化内容
                    DraftRuleSet(
                        ruleset_requirement="章节的`depend_on`字段的`ArticleRef`只能引用当前章节之前的元素。\n",
                        output_key="dep_ref_ruleset",
                        rule_count=1,
                    ),
                    DraftRuleSet(
                        ruleset_requirement="章节的`support_to`字段的`ArticleRef`只能引用当前章节之后的元素。\n",
                        output_key="rev_dep_ref_ruleset",
                        rule_count=1,
                    ),
                    DraftRuleSet(
                        ruleset_requirement="ArticleRef必须指向已定义元素",
                        output_key="ref_ruleset",
                        rule_count=1,
                    ),
                    DraftRuleSet(
                        ruleset_requirement="标题使用学术术语",
                        output_key="outline_ruleset",
                        rule_count=1,
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
        path = ok(await proposed_task.delegate(ns), "Failed to generate ruleset")
        logger.success(f"The outline is saved in:\n{path}")
    if fintune:
        proposed_task = Task(name="finetune an article")
        path = ok(await proposed_task.delegate(finetune), "Failed to generate ruleset")
        logger.success(f"The outline is saved in:\n{path}")


if __name__ == "__main__":
    asyncio.run(main(True, False, False))
