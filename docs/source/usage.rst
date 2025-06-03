Usage
=====

Basic Example
-------------

.. code-block:: python

   import asyncio
   from fabricatio import Action, Role, Task, logger, WorkFlow, Event
   from typing import Any


   class Hello(Action):
       name: str = "hello"
       output_key: str = "task_output"

       async def _execute(self, task_input: Task[str], **_) -> Any:
           return "Hello fabricatio!"

   async def main() -> None:
       Role(
           name="talker",
           description="talker role",
           registry={Event.quick_instantiate("talk"): WorkFlow(name="talk", steps=(Hello,))}
       )
       result = await Task(name="say hello").delegate("talk")
       logger.success(f"Result: {result}")

   if __name__ == "__main__":
       asyncio.run(main())
