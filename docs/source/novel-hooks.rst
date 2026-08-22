Novel Pipeline Hooks
====================

The ``fabricatio-novel`` package drives a four-level pipeline — **novel → chapter → story → scene** — through capability mixins. Extension points come in two families:

1. **Lifecycle hooks** — a symmetric trio defined at *every* level and wired identically into each ``compose_*`` entry point.
2. **Pipeline seams** — level-specific methods (planning phases, character-span drafting, prompt preparation) that subclasses override to inject behavior such as the setting bible or writing-style RAG.

Lifecycle Hooks
---------------

Every level exposes the same three hooks with identity defaults. They live on the capability classes and are invoked from that level's ``compose_*`` method — nowhere else.

.. list-table::
   :header-rows: 1

   * - Level
     - Mixin class
     - Before context
     - After context
     - Post-process artifact
   * - Novel
     - ``NovelCompose``
     - ``before_compose_novel(ctx)``
     - ``after_compose_novel(ctx)``
     - ``post_process_novel(ctx, novel)``
   * - Chapter
     - ``ChapterCompose``
     - ``before_compose_chapter(ctx)``
     - ``after_compose_chapter(ctx)``
     - ``post_process_chapter(ctx, chapter)``
   * - Story
     - ``StoryCompose``
     - ``before_compose_story(ctx)``
     - ``after_compose_story(ctx)``
     - ``post_process_story(ctx, story)``
   * - Scene
     - ``SceneCompose``
     - ``before_compose_scene(ctx)``
     - ``after_compose_scene(ctx)``
     - ``post_process_scene(ctx, scene)``

Contract:

* Before/after hooks receive and return the level's context; they may mutate it in place (e.g. enrich prompt channels).
* Post-process hooks receive the composed artifact plus its context and return the (possibly transformed) artifact.
* All hooks receive the caller's LLM ``**kwargs`` pass-through.
* Every default implementation is an identity function; overriding any of them is optional.

Wiring is byte-for-byte the same shape at all four levels:

.. code-block:: python

    async def compose_level(self, ctx, send_to=None, **kwargs):
        ctx = await self.before_compose_level(ctx, **kwargs)
        artifact = await self.generate_level(ctx, send_to, **kwargs)
        ctx = await self.after_compose_level(ctx, **kwargs)
        if artifact is None:
            return None
        return await self.post_process_level(ctx, artifact, **kwargs)

Because ``NovelCompose`` extends ``ChapterCompose`` extends ``StoryCompose`` extends ``SceneCompose``, one role composing a whole novel runs the scene hooks once per scene, story hooks once per story, and so on — inner levels nest inside outer ones.

Pipeline Seams
--------------

Beyond the lifecycle trio, each level's ``generate_*`` method calls named seams in a fixed order. The table lists them top-down in execution order.

.. list-table::
   :header-rows: 1

   * - Seam
     - Defined on
     - Fires during
     - Purpose
   * - ``propose_novel_metadata``
     - ``NovelCompose``
     - ``generate_novel``
     - Outline → ``NovelPlan`` (title, description, word budget, bible).
   * - ``prepare_character_span``
     - ``NovelCompose``
     - ``generate_novel``
     - Propose the roster: one ``CharacterSpan`` per bible character. Skipped when the bible has no roster.
   * - ``plan_chapters_phase``
     - ``NovelCompose``
     - ``generate_novel``
     - Plan chapters; then ``draft_chapter_spans`` proposes N−1 boundary cards per character.
   * - ``plan_stories_phase``
     - ``ChapterCompose``
     - ``generate_chapter``
     - Plan stories; then ``draft_story_spans`` proposes S−1 boundary cards per character.
   * - ``prepare_story``
     - ``SceneCompose`` *(see note)*
     - ``plan_scenes_phase``
     - Identity hook before a story's scenes are planned; RAG overrides it to retrieve writing styles.
   * - ``plan_scenes_phase``
     - ``StoryCompose``
     - ``generate_story``
     - Plan scenes for the story.
   * - ``prepare_scene_write``
     - ``StoryCompose``
     - ``generate_story``
     - Broadcast the story's span list and settings bible to every scene context.
   * - ``prepare_scene_requirement``
     - ``SceneCompose``
     - ``generate_scene``
     - Render the scene-prompt template variables; BibleCompose adds the bible block.
   * - ``render_bible_context``
     - ``BibleCompose``
     - ``generate_scene``
     - Render the (run-growable) bible section injected into scene prompts.

.. note::

   ``prepare_story`` is declared on ``SceneCompose``, not ``StoryCompose``: retrieval is scoped to a story, and the RAG mixin composes at the scene/story boundary. It is invoked from ``StoryCompose.plan_scenes_phase``.

Execution flow of a full generation:

.. mermaid::

   flowchart TD
      GN["generate_novel"] --> MD["propose_novel_metadata"]
      MD --> RS["prepare_character_span"]
      RS --> PC["plan_chapters_phase\ndraft_chapter_spans"]
      PC --> CC["compose_chapters_phase"]
      CC --> GC["generate_chapter\n(before/after/post_process_chapter)"]
      GC --> PS["plan_stories_phase\ndraft_story_spans"]
      PS --> CS["compose_stories_phase"]
      CS --> GS["generate_story\n(before/after/post_process_story)"]
      GS --> PSC["plan_scenes_phase\nprepare_story"]
      PSC --> PW["prepare_scene_write\nbroadcast spans + bible"]
      PW --> WCS["compose_scenes_phase"]
      WCS --> GSC["compose_scene\n(before/after/post_process_scene)\nprepare_scene_requirement"]

Production Overrides
--------------------

Two capabilities override seams without touching lifecycle hooks:

* ``BibleCompose`` (settings bible): overrides ``prepare_scene_requirement`` to merge ``render_bible_context`` output into every scene prompt.
* ``RAGCompose`` (writing-style RAG): overrides ``prepare_story`` to fetch ``WritingStyleDocument`` entries once per story; retrieved styles ride the context's writing-styles channel into scene prompts.

This is the intended extension pattern: subclass the level mixin whose seam you need, override only that seam, and leave the twelve lifecycle hooks at their defaults.

Symmetry Audit
--------------

**Lifecycle hooks: fully symmetric.** All four levels define all three hooks (12/12), with identical invocation order, signature shape, kwarg pass-through, and identity defaults.

Asymmetries elsewhere are deliberate:

* **Scenes inherit instead of drafting.** Novel→chapter and chapter→story boundaries get LLM-drafted boundary cards (``draft_chapter_spans``, ``draft_story_spans``); there is no ``draft_scene_spans``. Scenes share their story's arc verbatim via the ``prepare_scene_write`` broadcast — no extra LLM call.
* **Root-only seams.** ``propose_novel_metadata`` and ``prepare_character_span`` exist only at novel level: metadata and the character roster are novel-scoped by nature and have no meaningful counterpart below.
