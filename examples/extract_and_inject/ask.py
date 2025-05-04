"""Simple chat example."""

import asyncio

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio.capabilities.rag import RAG
from fabricatio.models.extra.aricle_rag import ArticleChunk
from fabricatio.utils import ok
from questionary import text


class Talk(Action, RAG):
    """Action that says hello to the world."""

    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> int:
        counter = 0

        self.init_client()

        try:
            while True:
                user_say = await text("User: ").ask_async()
                if user_say is None:
                    break
                ref_q = ok(await self.arefined_query(user_say))
                logger.info(f'refined query: \n{ref_q}')
                ret = await self.aretrieve(ref_q, document_model=ArticleChunk)

                sys_msg = "\n".join(r.as_prompt() for r in ret)
                logger.info(f"System message: \n{sys_msg}")
                gpt_say = await self.aask(user_say, sys_msg)

                print(f"GPT: {gpt_say}")  # noqa: T201
                counter += 1
        except KeyboardInterrupt:
            logger.info(f"executed talk action {counter} times")
        return counter


async def main() -> None:
    """Main function."""
    Role(
        name="talker",
        description="talker role but with rag",
        registry={
            Event.quick_instantiate("talk"): WorkFlow(name="talk", steps=(Talk(target_collection="article_chunks"),))
        },
    )

    task = Task(name="answer user's questions")
    _ = await task.delegate("talk")


if __name__ == "__main__":
    asyncio.run(main())
