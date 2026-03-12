"""Example of a poem writing program using fabricatio."""
from typing import Any, Optional

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio_core.capabilities.usages import UseLLM


# 可能会遇到LLM访问GitHub价格表连接失败的警告，可以无视。通常能访问本地价格表
# 在项目文件下，可以创建.env或fabricatio.toml等readme上的配置文件。
class WritePoem(Action, UseLLM):
    """Action that generates a poem."""

    output_key: str = "task_output"
    llm_stream: Optional[bool] = False

    async def _execute(self, task_input: Task[str], **_) -> Any:
        logger.info(f"Generating poem about \n{task_input.briefing}")
        return await self.ageneric_string(
            f"{task_input.briefing}\nWrite a poetic",
        )
    #task_input.briefing提炼Task的任务简述即喂给ai的提示词


# logger.info(f"{WritePoem.__mro__}") 查看继承
# print((dir(WritePoem)) ) 查看用法函数名

class WritePoem2(Action, UseLLM):
    """Action that generates a poem."""

    output_key: str = "task_output"
    llm_stream: Optional[bool] = False

    async def _execute(self, task_input: Task[str], **_) -> Any:
        logger.info(f"Generating poem about \n{task_input.briefing}")
        return await self.ageneric_string(
            f"说句包含晚安句子",
        )
    # 函数self.ageneric_string与ai交互，参数为提示词


role = Role(
        name="poet",
        description="A role that creates poetic content",
        skills={Event.quick_instantiate(ns := "poem").collapse(): WorkFlow(name="poetry_creation", steps=(WritePoem,))},
        # 通过参数skills直接初始的技能和其对应的工作流，后续可以通过add._skillt添加
).dispatch()
# add_skill 是类实例的方法
role.add_skill(event=Event.quick_instantiate("unlike"),
               workflow=WorkFlow(name="poetry_creation", steps=(WritePoem2,))
               ).dispatch()  # 需要再次激活

if __name__ == "__main__":
    task = Task(
        name="write poem",
        description="Write a poem about the given topic, in this case, write a poem about the fire",
        goals=["请用中文，7言2句，即可"],
    )

    poem = task.delegate_blocking("unlike")  # 寻找技能为ns的执行
    logger.info(f"Poem:\n\n{poem}")
