"""Event-level generation runtime — the generic base for the overhaul pipeline.

Design spec ``2026-08-08-novel-gen-overhaul-design.md`` §4.3b: the event
runtime mirrors today's :meth:`NovelCompose.create_chapters` exactly — a
feature-free base loop with no-op default hooks, a caller-owned sealed
channel, and capability mixins composed per novel via config (diamond MRO,
zero hook overrides in the combined class). Nothing capability-specific
(RAG/mental/state/illustration) is hard-wired into the base (D14).

Hooks chain via ``super()`` so sibling mixins all contribute through the
same seam. The capability itself stays stateless — all per-run state lives
in the caller-owned channel.
"""

from abc import ABC
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Unpack

from fabricatio_character.models.character import CharacterCard
from fabricatio_core.models.kwargs_types import ValidateKwargs
from fabricatio_core.rust import TASK

from fabricatio_novel.capabilities.novel import NovelCompose
from fabricatio_novel.models.chapter_context import ChapterContext
from fabricatio_novel.models.draft import NovelDraft
from fabricatio_novel.models.event_log import ChapterContract, EventIntent, EventLog, StoryEvent
from fabricatio_novel.models.novel import Novel
from fabricatio_novel.models.plan import ChapterPlan
from fabricatio_novel.models.scripting import Script
from fabricatio_novel.models.setting_bible import CoreSettingBible

if TYPE_CHECKING:
    from fabricatio_improve.models.improve import Improvement


class EventCompose(NovelCompose, ABC):
    """Base event-level runtime: splitter → per-event write → audit gate → commit.

    The base is generic and feature-free; all hooks have no-op defaults.
    Mixins SUBCLASS the sealed channel (:class:`ChapterContext` evolves with
    event-level fields) to carry their own cross-hook state; the base
    carries zero capability state (today's invariant, preserved).

    Entry point: :meth:`compose_novel` — the event-based replacement of
    :meth:`NovelCompose.compose_novel` (same signature, event-level
    internals): outline → bible → contracts → events → :class:`Novel`.
    """

    async def compose_novel(
        self,
        outline: str,
        language: Optional[str] = None,
        chapter_guidance: Optional[str] = None,
        *,
        bible: Optional[CoreSettingBible] = None,
        context: Optional[ChapterContext] = None,
        **kwargs: Unpack[ValidateKwargs[Novel]],
    ) -> Optional[Novel]:
        """Main novel composition pipeline (overhaul) — outline → bible → contracts → events → Novel.

        The event-based replacement of :meth:`NovelCompose.compose_novel`;
        same entry signature, event-level internals. Steps:

        1. Draft + characters (existing :meth:`generate_draft_and_characters`).
        2. Setting bible: the caller's (workflow-owned, D17) or pure-auto
           created from the outline via :meth:`create_setting_bible` (D2 —
           no interactive gate; the artifact IS the review).
        3. Plans (existing :meth:`generate_plans`) mapped onto chapter
           contracts via :meth:`derive_contracts`.
        4. Event generation (:meth:`compose_events`) — the full-auto gate
           (§4.3): intent → write → audit → commit / 回炉 ≤ N.
        5. Assembly (:meth:`assemble_novel_from_log`) — chapters are VIEWS
           of their events, derived from the log (regenerable exports, never
           a second truth).

        Args:
            outline: The novel outline (germ → draft input).
            language: Optional language override (auto-detected from the
                outline when omitted).
            chapter_guidance: Optional per-run writing guidance.
            bible: The run's setting bible; None → created pure-auto from
                the outline (D2).
            context: The sealed channel; default None → built via
                :meth:`build_chapter_context` (the overridable seam mixins
                use to return their own context subclass).
            **kwargs: Additional keyword arguments for LLM usage.

        Returns:
            The assembled :class:`Novel`, or None if any stage failed.
        """
        ...

    async def create_setting_bible(
        self,
        outline: str,
        language: Optional[str] = None,
        **kwargs: Unpack[ValidateKwargs[CoreSettingBible]],
    ) -> CoreSettingBible:
        """Phase 0a: pure-auto bible creation from the outline (D2 — no interactive gate).

        Chunked per section (§3.3, failure isolation): world (premise/tags/
        tone/selling_points/world_rules/factions) → characters → glossary
        (derived from world + characters output) → foreshadowing. Each chunk
        is pydantic-validated via ``propose`` and assembled into the
        ``novel_config.setting_bible_model`` subclass.

        Skeleton-first (D4): deliberate CORE SKELETON — enough 基础设定 to
        anchor consistency, NOT a complete bible. It grows via drift-
        triggered sync (§3.4, ≥3 candidate entities), never exhaustive
        upfront. Propose prompts live in ``templates/built-in/setting_bible_*.hbs``.

        Args:
            outline: The novel outline the bible is created from.
            language: Optional language override.
            **kwargs: Additional keyword arguments for LLM usage.

        Returns:
            The created bible (persistence is the caller's workflow concern, D17).
        """
        ...

    async def derive_contracts(
        self,
        chapter_plans: List[ChapterPlan],
        bible: CoreSettingBible,
        **kwargs: Unpack[ValidateKwargs[ChapterContract]],
    ) -> List[ChapterContract]:
        """Map the outline's chapter plans onto chapter contracts: 章末目标态 + 活跃线名单.

        Each contract declares where its chapter must land and which lines it
        moves — the chapter level of the two-level contract (§4.3). The
        splitter and the chapter-end target check consume these. [Exact
        derivation — LLM-enriched vs deterministic from the plan synopsis —
        verified at implementation; may batch with the script proposal to
        avoid a second call (§4.3a).]

        Args:
            chapter_plans: The per-chapter plans (synopses + scripts).
            bible: The run's setting bible (roster the active lines must reference).
            **kwargs: Additional keyword arguments for LLM usage.

        Returns:
            One contract per chapter, in order.
        """
        ...

    async def build_chapter_context(self, characters: List[CharacterCard]) -> ChapterContext:
        """Build the caller-owned channel for a run (overridable seam).

        Mixins override it to return their own context subclass carrying
        extra fields (state ledger, mental states, RAG config, …);
        ``compose_novel`` uses it when no ``context`` is passed. The base
        returns a plain :class:`ChapterContext`.

        Args:
            characters: The run's character cards (mixins may seed from them).
        """
        ...

    async def compose_events(
        self,
        bible: CoreSettingBible,
        contracts: List[ChapterContract],
        guidance: Optional[str] = None,
        send_to: str | None = TASK,
        *,
        context: Optional[ChapterContext] = None,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> EventLog:
        """Run the event pipeline: split → write → gate → commit, per event.

        Loop shape, per chapter contract:

        1. Split the contract into events (:meth:`split_chapter`).
        2. Per event: build the :class:`StoryEvent` (``seq = log.next_seq()``,
           ``parent = log.head_seq``), render the prompt
           (:meth:`prepare_event_prompt`), generate, stage on the channel
           (``ctx.set_pending_event``), run the full-auto gate
           (:meth:`run_event_gate` — 回炉 ≤ N, accept-best + quality debt on
           exhaustion), commit (append + fold lines), then fire
           :meth:`after_event_commit`.
        3. At each chapter boundary, derive the chapter-summary event from
           the chapter's scene events in the SAME call (hard rule — summaries
           are folds of their events, so they cannot contradict them).

        The returned log is the run's canonical artifact; the caller's
        workflow owns its persistence (D17).

        Args:
            bible: The run's setting bible (fixed context block + canonical roster).
            contracts: Per-chapter contracts (two-level contract, §4.3).
            guidance: Optional per-run writing guidance.
            send_to: The model group used for event generation.
            context: The sealed channel; default None → built via
                :meth:`build_chapter_context` (the overridable seam mixins
                use to return their own context subclass).
            **kwargs: Additional keyword arguments for LLM usage.

        Returns:
            The run's :class:`EventLog` (events + head + branches).
        """
        ...

    async def split_chapter(
        self,
        ctx: ChapterContext,
        bible: CoreSettingBible,
        contract: ChapterContract,
        **kwargs: Unpack[ValidateKwargs[Script]],
    ) -> List[EventIntent]:
        """Splitter: chapter contract → event sequence (§4.3a, B1).

        Evolved :meth:`NovelCompose.create_scripts`: the LLM proposes a
        :class:`Script` whose scenes carry ``weight`` and ``line_targets``;
        deterministic code then groups consecutive scenes (same
        location/when, weight-sum within bounds) into events and allocates
        word counts weight-proportionally (largest-remainder rounding, the
        illustration ``_allocate_image_budget`` pattern). The model freely
        assigns each scene's weight — no second LLM call for declarations.

        Args:
            ctx: The sealed channel (its event log supplies the memory slice
                and line current states the splitter reads).
            bible: The setting bible (contract facts the splitter honors).
            contract: The chapter contract to split.
            **kwargs: Additional keyword arguments for LLM usage.
        """
        ...

    async def prepare_event_prompt(self, ctx: ChapterContext, event: StoryEvent) -> str:
        """Hook: build and render the event prompt (mirror of ``prepare_chapter_prompt``).

        The default builds the base vars via :meth:`prepare_event_prompt_vars`,
        merges the vars the :meth:`extra_event_prompt_vars` hook wrote to
        ``ctx.chapter_prompt_vars``, and renders the event requirement
        template. Subclasses override to swap the template or inject extra
        fields — and SHOULD delegate to ``await super().prepare_event_prompt(ctx, event)``
        so sibling mixins still contribute through the same seam.

        Args:
            ctx: The sealed channel (inputs set by the loop).
            event: The event being prepared (intent + line_targets).
        """
        ...

    def prepare_event_prompt_vars(self, ctx: ChapterContext, event: StoryEvent) -> Dict[str, Any]:
        """Base template vars for the event requirement — the fixed-budget assembly (§4.4).

        ``context(N+1)`` = 固定块 (bible excerpts + style/format block +
        chapter contract, ~700 tokens) + 近程 (recent K=3 events, ~600) +
        线状态 (active line current states, ≤5, ~400) + 远记忆 (line-trail
        summaries of old chapters, ≤3, ~300) — O(1) tokens per event
        regardless of novel length. The log remembers; the model carries a
        slice.

        Args:
            ctx: The sealed channel (event log + contract).
            event: The event being prepared.
        """
        ...

    def extra_event_prompt_vars(self, ctx: ChapterContext, event: StoryEvent) -> None:
        """Hook: contribute extra template vars for the event prompt (no-op default).

        Mixins add feature-specific context (state boards, mental states,
        style docs, …) via ``ctx.add_prompt_vars``; the base
        :meth:`prepare_event_prompt` merges them into the render. Called once
        per event with the same ``ctx`` channel as the prompt hook.

        Args:
            ctx: The sealed channel (inputs set by the loop).
            event: The event being prepared.
        """
        ...

    async def after_event_gen(self, ctx: ChapterContext, event: StoryEvent) -> None:
        """Hook: audit/revise the just-generated event BEFORE the gate (no-op default).

        Fires right after generation, with the raw event staged via
        ``ctx.set_pending_event`` and before :meth:`audit_event` runs. The
        hook may replace the staged event (e.g. regeneration on violations);
        the gate audits the FINAL text.

        Args:
            ctx: The sealed channel (the staged event is at ``ctx.pending_event``).
            event: The event being generated.
        """
        ...

    async def audit_event(self, ctx: ChapterContext, event: StoryEvent) -> List["Improvement"]:
        """Hook: the full-auto gate's audit pass. Empty list = pass (D10).

        Base dimensions: 覆盖性 (intent + line_targets vs text) +
        deterministic core (bible rules/terms/dupes — pure Python) +
        universal quality (AI-tells/节奏, LLM-judged). Mixins add dimensions
        by chaining ``super()`` (mental: 情绪一致性; state: 线状态核对; rag:
        风格遵守; illustration: 图像场景可用性…). Style constraints (格式/
        尺度/禁忌) are audited via the rule package's
        ``Check.check_string(text, RuleSet)`` → Improvements (D16).

        NEVER call interactive paths (``supervisor_check`` — questionary) in
        this full-auto pipeline; use the non-interactive
        ``final_solution``/``decided`` path.

        Args:
            ctx: The sealed channel.
            event: The event to audit.

        Returns:
            Findings; empty list means the event passes the gate.
        """
        ...

    async def after_event_commit(self, ctx: ChapterContext, event: StoryEvent) -> None:
        """Hook: react to a committed event (no-op default).

        Fires after the event is appended to the log and the line web is
        folded. Mixins evolve their cross-hook state in the caller-owned
        channel here (the capability itself stays stateless).

        Args:
            ctx: The sealed channel.
            event: The just-committed event.
        """
        ...

    async def derive_chapter_summary(
        self,
        ctx: ChapterContext,
        chapter_index: int,
        **kwargs: Unpack[ValidateKwargs[StoryEvent]],
    ) -> Optional[StoryEvent]:
        """Derive the chapter-summary event from its scene events — SAME call, never independent.

        Hard rule: summaries are folds of their events, so they cannot
        contradict them. The derived event has ``group="chapter"``,
        ``source="verifier"``, and its content is the existing
        :class:`ChapterSummary` shape (key_events/character_states/
        unresolved_threads/established_facts/…). These power distant memory
        (§4.4) and the audits.

        Args:
            ctx: The sealed channel (the chapter's scene events live in its log).
            chapter_index: The chapter whose events are being folded.
            **kwargs: Additional keyword arguments for LLM usage.

        Returns:
            The summary event, or None if derivation failed (the chapter
            then simply has no summary event).
        """
        ...

    async def run_event_gate(
        self,
        ctx: ChapterContext,
        event: StoryEvent,
        max_retries: int = 2,
        **kwargs: Unpack[ValidateKwargs[str]],
    ) -> Tuple[bool, List["Improvement"]]:
        """Full-auto gate for one event (D10): audit → commit or 回炉 ≤ ``max_retries``.

        Pass → commit (append + fold lines + chapter-end target check). Fail
        → regenerate with the audit findings fed back through
        :meth:`after_event_gen`, up to ``max_retries`` (v1 default: 2). On
        exhaustion the BEST attempt is accepted and the findings become
        quality debt (Improvement + ``event_seq`` refs) for the edit phases —
        the draft never blocks (the two-hat principle still governs the HEAVY
        passes: chapter-end checks, copyedit, developmental — they never
        block here).

        Args:
            ctx: The sealed channel.
            event: The staged event to gate.
            max_retries: 回炉 bound (v1 default 2).
            **kwargs: Additional keyword arguments for LLM usage.

        Returns:
            (committed, final_findings) — ``committed`` is False only when
            the retry budget is exhausted and the best attempt was accepted
            with debt.
        """
        ...

    @staticmethod
    def assemble_novel_from_log(
        draft: NovelDraft,
        chapter_plans: List[ChapterPlan],
        event_log: EventLog,
        characters: List[CharacterCard],
    ) -> Novel:
        """Assemble the final novel from the event log — chapters are VIEWS of their events.

        The event-based successor of :meth:`NovelCompose.assemble_novel`
        (``chapter_contents`` → ``event_log``): each chapter's text is the
        fold of its scene events (in order, from the log's active chain);
        titles/word counts come from the plans; the novel shell from the
        draft. Derived, regenerable — never a second truth (D7).

        Args:
            draft: The novel draft (title/synopsis/word count).
            chapter_plans: The per-chapter plans (titles + synopses).
            event_log: The run's event log (the only structured body).
            characters: The character cards (kept for downstream consumers
                such as illustration; the bible is the canonical roster).

        Returns:
            The assembled :class:`Novel`.
        """
        ...
