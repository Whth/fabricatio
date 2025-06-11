"""Example of using the library."""

from pathlib import Path

from fabricatio import Action, Event, Role, Task, WorkFlow
from fabricatio.capabilities import Lyricize
from fabricatio_core.utils import ok
from fabricatio_yue.models.segment import Song


class Compose(Action, Lyricize):
    """Compose a song."""

    async def _execute(self, req: str, output: Path, **cxt) -> Song:
        return ok(await self.lyricize(req)).save_to(output)


(
    Role()
    .register_workflow(Event.quick_instantiate(ns := "generate_deck"), WorkFlow(steps=(Compose().to_task_output(),)))
    .dispatch()
)

generated_song: Song = ok(
    Task(name="gen deck")
    .update_init_context(
        req="Write a folk-rock song about finding hope in difficult times, with verses about struggle and a uplifting "
        "chorus about perseverance. Include bridge section with introspective lyrics.",
        output="here",
    )
    .delegate_blocking(ns)
)
