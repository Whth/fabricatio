"""Example of a simple hello world program using fabricatio."""
from typing import Any

from fabricatio import Action, Event, Role, Task, WorkFlow, logger

from fabricatio.capabilities import UseLLM

class say(Action):
    async def _execute(self, *_: Any, **cxt) -> Any:
        ret_1 = "你好 or hello"
        return ret_1


class Hello(Action):  # 类名即为动作名称
    """Action that says hello."""

    output_key: str = "task_output"  # 键名，但目前好像不支持被workflow自定义捕获,建议使用:"task_output"

    async def _execute(self, **_) -> Any:  # 该函数返回值会被储存在上下文字典中
        ret_2 = "说话 or say"
        logger.info("No")  # 打印日志
        return ret_2


# 创建 workflow 时明确指定所有参数
work = WorkFlow(
    name="事情1",  # 名称
    steps=(Hello, say,),  # 执行的动作，可多动作
    task_output_key="take1"  # 目前不支持自定义，其值为:"task_output",且默认取最后一个动作的结果
)

(
    Role(name="ai", description="不清楚")  # 角色名称和描述
    .add_skill(Event.quick_instantiate("123"), work)  # 事件("123")(作者称作技能，嘿嘿)可以触发该角色并执行workflow
    .dispatch()  # 激活该角色，不激活遇到该事件也不会执行
)

result = Task(name="1").delegate_blocking("123")  # 创建Task任务，并由事件\技能("123")的角色行动
logger.info(f"Result: {result}")
if result is not None:
    logger.info(result)


