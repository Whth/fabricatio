"""Example of using the library."""

from fabricatio import Event, Role, Task, WorkFlow
from fabricatio.actions import Compose
from fabricatio.models import Song
from fabricatio_core.utils import ok

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
