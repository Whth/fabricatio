"""Example of using DiffEdit capability to fix spelling and wording in an essay.

This demonstrates fabricatio's diff editing feature by correcting common writing errors
in a Chinese student essay while preserving the original content structure and meaning.
"""

from typing import Optional

from fabricatio import Action, Event, Role, Task, WorkFlow, logger
from fabricatio.capabilities import DiffEdit

essay_to_fix = """
In my learn jorney, there is many teacher taht tought me, but the most i respect is our class moniter, Miss Li. She not only teach very carefull, but also care about every student very much.

I remmember one time, I got a cold and had a faver, so I took a leav and stay at home to resst. I think nobady would knows, but in the afternon, Teacher Li call me and ask if I feeling better. She told me to drink more water and take my medcin on time. What moved me most is that, the next day in scool, she lend me her note to copy, because she worry I will miss leson. Her handwritting is very tidy and clearly, and she mark all the importent point with red pen. She is so thoughtfull!

Teacher Li never get mad in class, even when some student make trouble, she alway patient talk to them, never shout loud. She use to say: "Every student is a seeed, if you water it with heart, it will grow and bloosom one day." This word alway give me strenght and make me not slak in study.

One time, I did very bad in math exam, I feel very upset. Teacher Li not blame me, insted, she gently pat my sholder and say: "Failer is the moddy of sucsess. If you dont give up, you will make progres." Her word is like sunshin, warm my hart.

Altho Teacher Li is strict somtimes, we all know she want us to be sucseful. She is like a lamp, shine the way of our grow.

When I grow up, I want to be a teacher just like Teacher Li, a hartful and responible new era teacher. She is my forever role modle."""


class TweakEssay(Action, DiffEdit):
    """An action that fixes spelling mistakes and word usage in essays using diff editing.

    Attributes:
        essay: The input essay text to be corrected, optional until execution.
    """

    essay: Optional[str] = None

    async def _execute(self, essay: Optional[str], **cxt) -> str:
        """Executes the essay correction process.

        Args:
            essay: The text content to be corrected
            **cxt: Additional execution context (unused)

        Returns:
            str: The corrected essay text with suggested improvements
        """
        logger.info(f"Tweaking essay... words: {len(essay)}")
        return await self.diff_edit(essay, "fix all spelling mistakes and typo or wrong usage of words in the essay.")


# Configure role workflow for essay tweaking
Role(name="writer").register_workflow(
    Event.quick_instantiate("tweak"), WorkFlow(name="tweak flow", steps=(TweakEssay().to_task_output(),))
).dispatch()


# Create and execute the essay correction task
new_essay = Task(name="tweak essay").update_init_context(essay=essay_to_fix).delegate_blocking("tweak")
