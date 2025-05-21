"""Dump the finalized output to a file."""

from pathlib import Path
from typing import Any, Iterable, List, Mapping, Optional, Self, Sequence, Type

from fabricatio_capabilities.models.generic import FinalizedDumpAble, PersistentAble
from fabricatio_core.fs import dump_text
from fabricatio_core.journal import logger
from fabricatio_core.models.action import Action
from fabricatio_core.models.task import Task
from fabricatio_core.models.usages import LLMUsage
from fabricatio_core.rust import TEMPLATE_MANAGER
from fabricatio_core.utils import ok

from fabricatio_actions.models.generic import FromMapping, FromSequence


class DumpFinalizedOutput(Action, LLMUsage):
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
        logger.info(f"Saving output to {dump_path.as_posix()}")
        ok(to_dump, "Could not dump the data since the path is not specified.").finalized_dump_to(dump_path)
        return dump_path.as_posix()


class RenderedDump(Action, LLMUsage):
    """Render the data to a file."""

    output_key: str = "dump_path"
    dump_path: Optional[str] = None

    template_name: str
    """The template name to render the data."""

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

        logger.info(f"Saving output to {dump_path.as_posix()}")
        dump_text(
            dump_path,
            TEMPLATE_MANAGER.render_template(
                self.template_name, {to_dump.__class__.__name__: to_dump.finalized_dump()}
            ),
        )

        return dump_path.as_posix()


class PersistentAll(Action, LLMUsage):
    """Persist all the data to a file."""

    output_key: str = "persistent_count"
    """The number of objects persisted."""
    persist_dir: Optional[str] = None
    """The directory to persist the data."""
    override: bool = False
    """Whether to remove the existing dir before dumping."""

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
        if self.override and persist_dir.is_dir():
            logger.info(f"Override the existing directory {persist_dir.as_posix()}.")
            persist_dir.rmdir()
        logger.info(f"Starting persistence in directory {persist_dir}")
        for k, v in cxt.items():
            final_dir = persist_dir.joinpath(k)
            logger.debug(f"Checking key {k} for persistence")
            if isinstance(v, PersistentAble):
                logger.info(f"Persisting object {k} to {final_dir}")
                final_dir.mkdir(parents=True, exist_ok=True)
                v.persist(final_dir)
                count += 1
            if isinstance(v, Iterable) and any(
                persistent_ables := (pers for pers in v if isinstance(pers, PersistentAble))
            ):
                logger.info(f"Persisting collection {k} to {final_dir}")
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

    async def _execute(self, /, **_) -> Optional[T | List[T]]:
        logger.info(f"Retrieve `{self.retrieve_cls.__name__}` from {self.load_path}")
        if not (p := Path(self.load_path)).exists():
            logger.warning(f"Path {self.load_path} does not exist")
            return None

        if p.is_dir():
            logger.info(f"Found directory with {len(list(p.glob('*')))} items")
            return [self.retrieve_cls.from_persistent(per) for per in p.glob("*")]
        return self.retrieve_cls.from_persistent(self.load_path)


class RetrieveFromLatest[T: PersistentAble](RetrieveFromPersistent[T], FromMapping):
    """Retrieve the object from the latest persistent file in the dir at `load_path`."""

    async def _execute(self, /, **_) -> Optional[T]:
        logger.info(f"Retrieve latest `{self.retrieve_cls.__name__}` from {self.load_path}")
        if not (p := Path(self.load_path)).exists():
            logger.warning(f"Path {self.load_path} does not exist")
            return None

        if p.is_dir():
            logger.info(f"Found directory with {len(list(p.glob('*')))} items")
            return self.retrieve_cls.from_latest_persistent(self.load_path)
        logger.error(f"Path {self.load_path} is not a directory")
        return None

    @classmethod
    def from_mapping(
        cls,
        mapping: Mapping[str, str | Path],
        *,
        retrieve_cls: Type[T],
        **kwargs,
    ) -> List["RetrieveFromLatest[T]"]:
        """Create a list of `RetrieveFromLatest` from the mapping."""
        return [
            cls(retrieve_cls=retrieve_cls, load_path=Path(p).as_posix(), output_key=o, **kwargs)
            for o, p in mapping.items()
        ]


class GatherAsList(Action):
    """Gather the objects from the context as a list.

    Notes:
        If both `gather_suffix` and `gather_prefix` are specified, only the objects with the suffix will be gathered.
    """

    output_key: str = "gathered"
    """Gather the objects from the context as a list."""
    gather_suffix: Optional[str] = None
    """Gather the objects from the context as a list."""
    gather_prefix: Optional[str] = None
    """Gather the objects from the context as a list."""

    async def _execute(self, **cxt) -> List[Any]:
        if self.gather_suffix is not None:
            result = [cxt[k] for k in cxt if k.endswith(self.gather_suffix)]
            logger.debug(f"Gathered {len(result)} items with suffix {self.gather_suffix}")
            return result
        if self.gather_prefix is None:
            logger.error(err := "Either `gather_suffix` or `gather_prefix` must be specified.")
            raise ValueError(err)
        result = [cxt[k] for k in cxt if k.startswith(self.gather_prefix)]
        logger.debug(f"Gathered {len(result)} items with prefix {self.gather_prefix}")
        return result


class Forward(Action, FromMapping, FromSequence):
    """Forward the object from the context to the output."""

    output_key: str = "forwarded"
    """Gather the objects from the context as a list."""
    original: str

    async def _execute(self, *_: Any, **cxt) -> Any:
        source = cxt.get(self.original)
        if source is None:
            logger.warning(f"Original object {self.original} not found in the context")
        return source

    @classmethod
    def from_sequence(cls, sequence: Sequence[str], *, original: str, **kwargs: Any) -> List[Self]:
        """Create a list of `Forward` from the sequence."""
        return [cls(original=original, output_key=o, **kwargs) for o in sequence]

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, str | Sequence[str]], **kwargs: Any) -> List[Self]:
        """Create a list of `Forward` from the mapping."""
        actions = []
        for original_key, output_val in mapping.items():
            if isinstance(output_val, str):
                actions.append(cls(original=original_key, output_key=output_val, **kwargs))
            elif isinstance(output_val, Sequence):
                actions.extend(cls(original=original_key, output_key=output_key, **kwargs) for output_key in output_val)
            else:
                logger.warning(
                    f"Invalid type for output key value in mapping: {type(output_val)} for original key {original_key}. Expected str or Sequence[str]."
                )
        return actions
