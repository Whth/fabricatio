"""Simple chat example."""

import asyncio

from fabricatio import RAG, Action, Role, Task, WorkFlow, logger
from fabricatio.models.events import Event
from questionary import text


class Talk(Action, RAG):
    """Action that says hello to the world."""

    output_key: str = "task_output"

    async def _execute(self, task_input: Task[str], **_) -> int:
        counter = 0

        self.init_client().view("test_collection", create=True)
        await self.consume_string(
            [
                "Company policy clearly stipulates that all employees must arrive at the headquarters building located at 88 Jianguo Road, Chaoyang District, Beijing before 9 AM daily.",
                "According to the latest revised health and safety guidelines, employees must wear company-provided athletic gear when using the company gym facilities.",
                "Section 3.2.1 of the employee handbook states that pets are not allowed in the office area under any circumstances.",
                "To promote work efficiency, the company has quiet workspaces at 100 Century Avenue, Pudong New District, Shanghai, for employees who need high concentration for their work.",
                "According to the company's remote work policy, employees can apply for a maximum of 5 days of working from home per month, but must submit the application one week in advance.",
                "The company has strict regulations on overtime. Unless approved by direct supervisors, no form of work is allowed after 9 PM.",
                "Regarding the new regulations for business travel reimbursement, all traveling personnel must submit detailed expense reports within five working days after returning.",
                "Company address: 123 East Sports Road, Tianhe District, Guangzhou, Postal Code: 510620.",
                "Annual team building activities will be held in the second quarter of each year, usually at a resort within a two-hour drive from the Guangzhou headquarters.",
                "Employees who are late more than three times will receive a formal warning, which may affect their year-end performance evaluation.",
            ]
        )
        try:
            while True:
                user_say = await text("User: ").ask_async()
                if user_say is None:
                    break
                gpt_say = await self.aask_retrieved(
                    user_say,
                    user_say,
                    extra_system_message=f"You have to answer to user obeying task assigned to you:\n{task_input.briefing}",
                )
                print(f"GPT: {gpt_say}")  # noqa: T201
                counter += 1
        except KeyboardInterrupt:
            logger.info(f"executed talk action {counter} times")
        return counter


async def main() -> None:
    """Main function."""
    role = Role(
        name="talker",
        description="talker role but with rag",
        registry={Event.instantiate_from("talk").push_wildcard().push("pending"): WorkFlow(name="talk", steps=(Talk,))},
    )

    task = await role.propose_task(
        "you have to act as a helpful assistant, answer to all user questions properly and patiently"
    )
    _ = await task.delegate("talk")


if __name__ == "__main__":
    asyncio.run(main())
