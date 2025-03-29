"""Dump the finalized output to a file."""

from pathlib import Path
from typing import Iterable, List, Optional, Type

from fabricatio.journal import logger
from fabricatio.models.action import Action
from fabricatio.models.generic import FinalizedDumpAble, PersistentAble
from fabricatio.models.task import Task
from fabricatio.utils import ok


class DumpFinalizedOutput(Action):
    """Dump the finalized output to a file."""

    output_key: str = "dump_path"
    dump_path: Optional[str] = None

    async def _execute(
        self,
        to_dump: FinalizedDumpAble,
        task_input: Optional[Task] = None,
        dump_path: Optional[str | Path] = None,
        **_,
    ) -> str:
        dump_path = Path(
            dump_path
            or self.dump_path
            or ok(
                await self.awhich_pathstr(
                    f"{ok(task_input, 'Neither `task_input` and `dump_path` is provided.').briefing}\n\nExtract a single path of the file, to which I will dump the data."
                ),
                "Could not find the path of file to dump the data.",
            )
        )
        ok(to_dump, "Could not dump the data since the path is not specified.").finalized_dump_to(dump_path)
        return dump_path.as_posix()


class PersistentAll(Action):
    """Persist all the data to a file."""

    output_key: str = "persistent_count"
    persist_dir: Optional[str] = None

    async def _execute(
        self,
        task_input: Optional[Task] = None,
        persist_dir: Optional[str | Path] = None,
        **cxt,
    ) -> int:
        persist_dir = Path(
            persist_dir
            or self.persist_dir
            or ok(
                await self.awhich_pathstr(
                    f"{ok(task_input, 'Neither `task_input` and `dump_path` is provided.').briefing}\n\nExtract a single path of the file, to which I will persist the data."
                ),
                "Can not find the path of file to persist the data.",
            )
        )

        count = 0
        if persist_dir.is_file():
            logger.warning("Dump should be a directory, but it is a file. Skip dumping.")
            return count

        for k, v in cxt.items():
            final_dir = persist_dir.joinpath(k)
            if isinstance(v, PersistentAble):
                final_dir.mkdir(parents=True, exist_ok=True)
                v.persist(final_dir)
                count += 1
            if isinstance(v, Iterable) and any(
                persistent_ables := (pers for pers in v if isinstance(pers, PersistentAble))
            ):
                final_dir.mkdir(parents=True, exist_ok=True)
                for per in persistent_ables:
                    per.persist(final_dir)
                    count += 1
        logger.info(f"Persisted {count} objects to {persist_dir}")
        return count


class RetrieveFromPersistent[T: PersistentAble](Action):
    """Retrieve the object from the persistent file."""

    output_key: str = "retrieved_obj"
    """Retrieve the object from the persistent file."""
    load_path: str
    """The path of the persistent file or directory contains multiple file."""
    retrieve_cls: Type[T]
    """The class of the object to retrieve."""

    async def _execute(self, /, **__) -> Optional[T | List[T]]:
        logger.info(f"Retrieve `{self.retrieve_cls.__name__}` from persistent file: {self.load_path}")
        if not (p := Path(self.load_path)).exists():
            return None

        if p.is_dir():
            return [self.retrieve_cls.from_persistent(per) for per in p.glob("*")]
        return self.retrieve_cls.from_persistent(self.load_path)
