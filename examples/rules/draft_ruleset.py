"""Example of using the library."""

import asyncio
from typing import TYPE_CHECKING

from fabricatio import Event, Role, WorkFlow, logger
from fabricatio.actions.output import PersistentAll
from fabricatio.actions.rules import DraftRuleSet
from fabricatio.models.task import Task
from fabricatio.utils import ok

if TYPE_CHECKING:
    from fabricatio.models.extra.rule import RuleSet


async def main() -> None:
    """Main function."""
    Role(
        name="Undergraduate Researcher",
        llm_model="openai/qwen-plus",
        llm_rpm=1000,
        llm_tpm=3000000,
        llm_max_tokens=8190,
        registry={
            Event.quick_instantiate(ns := "article"): WorkFlow(
                name="write ruleset",
                description="Generate a draft ruleset for article.",
                steps=(
                    DraftRuleSet(
                        ruleset_requirement="1.when try to use an article as reference cited in our article, you should obey the format like `(author1, author2 et al., YYYY)#cite(<bibtex_cite_key>)`\n"
                        "2.we use typst to generate numeric citation. For example, for an article whose `bibtex_key` is `YanWindEnergy2018`, you can create a numeric citation by typing `#cite(<YanWindEnergy2018>)`(note that `bibtex_key` with `<` and `>` wrapped is needed), those notations could automatically be processed and output by compiler as a numeric citation like `[1]` in the upper right corner of text.\n"
                        "3.in addition, since `#cite()` can ONLY cite ONE article at once, we need use multiple `#cite()` notations to cite multiple articles, for example, there are three articles whose `bibtex_key` are `YanWindEnergy2018`, `YanWindEnergy2019`, `YanWindEnergy2020, you can cite them three as numeric citation by typing `#cite(<YanWindEnergy2018>)#cite(<YanWindEnergy2019>)#cite(<YanWindEnergy2020>)` those notations could automatically be processed and output by compiler as a numeric citation like `[1,2,3]` in the upper right corner of text.\n"
                        "4.to cover more references, we usually cite more than one articles that have similar opinions in a single sentence if possible.\n"
                        "5.when using `#cite()` notation, you must be aware of the cite key should be wrapped by `<` and `>`, compiler wont let it pass compilation otherwise.",
                        rule_count=5,
                        output_key="en_ruleset"
                    ),
                    DraftRuleSet(
                        ruleset_requirement="1. 当在文章中引用其他文章作为参考文献时, 应遵循`(作者1, 作者2等, 年份)#cite(<bibtex_cite_key>)`的格式进行标注。\n"
                        "2. 我们使用Typst生成数字引用格式。例如, 对于BibTeX键为`YanWindEnergy2018`的文献, 可通过输入`#cite(<YanWindEnergy2018>)`创建数字引用(注意:BibTeX键必须用尖括号`<`和`>`包裹)。这些标记会被编译器自动处理并输出为右上角的数字引用格式, 例如文本旁的[1]。\n"
                        "3. 此外, 由于`#cite()`每次只能引用单一文献, 需通过叠加多个`#cite()`标记实现多文献引用。例如, 若需引用三个BibTeX键分别为`YanWindEnergy2018`、`YanWindEnergy2019`和`YanWindEnergy2020`的文献, 应输入`#cite(<YanWindEnergy2018>)#cite(<YanWindEnergy2019>)#cite(<YanWindEnergy2020>)`, 编译后将呈现为[1,2,3]的右上角数字引用格式。\n"
                        "4. 为增加参考文献的覆盖率, 我们通常建议在可能的情况下, 将多个观点相似的文献合并引用于同一句子中。"
                        "5. 使用`#cite()`时需注意:BibTeX键必须用尖括号`<`和`>`包裹, 否则编译器将拒绝通过编译。",
                        rule_count=5,
                        output_key="zh_ruleset"
                    ),
                    PersistentAll(persist_dir="persistent"),
                ),
            )
        },
    )

    proposed_task: Task[RuleSet] = Task(name="write an ruleset")
    ruleset = ok(await proposed_task.delegate(ns), "Failed to generate ruleset")
    logger.success(f"The rule is: \n{ruleset.display()}")


if __name__ == "__main__":
    asyncio.run(main())
