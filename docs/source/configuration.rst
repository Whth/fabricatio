Configuration Guide
===================

Fabricatio uses a single, layered configuration chain shared by the Rust core and every
Python subpackage. This guide documents how the sources are linked, every option of the
core sections, and the per-package (extension) configuration surface.

.. contents::
   :local:
   :depth: 2

How Configuration Sources Are Linked
------------------------------------

All sources are merged into one ``Config`` tree by `figment
<https://docs.rs/figment>`_. The loader (``crates/fabricatio-config/src/config_loader.rs``)
builds this chain:

.. code-block:: rust

   Figment::new()
       .join(Env::prefixed("FABRICATIO_").split("__"))          // 1. environment
       .join(Toml::file("fabricatio.toml"))                     // 2. project file
       .join(PyprojectToml("./pyproject.toml", ["tool", "fabricatio"]))
                                                                // 3. pyproject
       .join(Toml::file(GLOBAL_CONFIG_FILE))                    // 4. global file
       .join(Config::default());                                // 5. built-in defaults

The first provider joined wins. The resulting priority order (highest to lowest):

#. **Call arguments** — programmatic overrides at the Python call site (for example
   ``aask(..., send_to="other")``). These live above the config chain entirely.
#. **``./.env``** — loaded by ``dotenvy`` *before* the environment layer is read;
   variables defined here override same-named process environment variables.
#. **Environment variables** — any variable starting with ``FABRICATIO_``.
#. **``./fabricatio.toml``** — the working-directory configuration file.
#. **``./pyproject.toml``** under the ``[tool.fabricatio]`` table.
#. **Global config file** — ``<ROAMING>/fabricatio/fabricatio.toml``.
#. **Built-in defaults** — compiled into the config structs.

Merging is **per key**, not per file: a value set in a high-priority source overrides only
that single leaf; all other leaves keep their values from lower-priority sources. For
example, you can keep providers in ``fabricatio.toml`` and still override just the log
level with ``FABRICATIO_DEBUG__LOG_LEVEL=DEBUG``.

Environment variable syntax
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Prefix with ``FABRICATIO_`` and nest with double underscores. Keys are matched
case-insensitively:

.. code-block:: ini

   FABRICATIO_LLM__TEMPERATURE=0.7      # -> [llm] temperature
   FABRICATIO_DEBUG__LOG_LEVEL=DEBUG    # -> [debug] log_level
   FABRICATIO_EXT__WEBUI__ADDR=0.0.0.0:9846   # -> [ext.webui] addr (extension config)

Scalar values (strings, numbers, booleans) work well through environment variables. For
complex values such as the routing provider/deployment lists, prefer one of the TOML
files.

File locations
~~~~~~~~~~~~~~

The global file lives in the platform configuration directory:

.. list-table::
   :header-rows: 1
   :widths: 15 45 40

   * - Platform
     - Config directory
     - Global config file
   * - Linux
     - ``$XDG_CONFIG_HOME`` or ``~/.config``
     - ``~/.config/fabricatio/fabricatio.toml``
   * - macOS
     - ``~/Library/Application Support``
     - ``~/Library/Application Support/fabricatio/fabricatio.toml``
   * - Windows
     - ``%APPDATA%`` (Roaming)
     - ``%APPDATA%\fabricatio\fabricatio.toml``

Only ``fabricatio.toml`` is discovered automatically; alternative files (staging,
production) must be copied or symlinked onto one of the discovered paths, or replaced by
environment-variable overrides.

Quick Start
-----------

#. Install Fabricatio:

   .. code-block:: bash

      pip install fabricatio[full]     # or: uv add fabricatio[full]

#. Create ``fabricatio.toml`` next to your code:

   .. code-block:: toml

      [debug]
      log_level = "INFO"

      [llm]
      send_to = "base"

      [routing]
      providers = [
          { ptype = "OpenAICompatible", key = "sk-your-key", name = "openai",
            base_url = "https://api.openai.com/v1/" }
      ]
      completion_deployments = [
          { id = "openai/gpt-4o-mini", group = "base", tpm = 100_000, rpm = 1000 }
      ]

#. Smoke-test it:

   .. code-block:: python

      from fabricatio import Action, Event, Role, Task, WorkFlow

      class Hello(Action):
          output_key: str = "greeting"
          async def _execute(self, **_) -> str:
              return await self.aask("Say hi in one sentence")

      (
          Role(name="greeter")
          .subscribe(Event.quick_instantiate("greet"), WorkFlow(name="greet", steps=(Hello,)))
          .dispatch()
      )
      print(Task(name="demo").delegate_blocking("greet"))

Core Sections Reference
-----------------------

Every core section is defined in ``crates/fabricatio-config/src/configs.rs``. Unknown
top-level tables in the TOML files are ignored; extension packages are configured under
``[ext.*]`` instead (see :ref:`extension-config`).

[debug]
~~~~~~~

Logging configuration.

.. list-table::
   :header-rows: 1
   :widths: 25 15 20 40

   * - Option
     - Type
     - Default
     - Description
   * - ``log_level``
     - string
     - ``"INFO"``
     - Log verbosity (e.g. ``TRACE``, ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``).
   * - ``log_dir``
     - path
     - *(unset)*
     - Optional directory for log files.
   * - ``rotation``
     - string
     - *(unset)*
     - Optional log rotation policy.

[llm]
~~~~~

Default parameters for completion requests. All sampling options can still be overridden
per call.

.. list-table::
   :header-rows: 1
   :widths: 30 15 20 35

   * - Option
     - Type
     - Default
     - Description
   * - ``send_to``
     - string
     - *(unset)*
     - Routing group (or :ref:`agent variant <agent-config>`) used when a request does
       not name one. If unset everywhere, requests fail with "send_to is not specified".
   * - ``no_cache``
     - bool
     - *(unset)*
     - Bypass the response cache for completions.
   * - ``temperature``
     - float
     - *(unset)*
     - Sampling temperature. Validated range 0.0–2.0.
   * - ``top_p``
     - float
     - *(unset)*
     - Nucleus sampling threshold. Validated range 0.0–1.0.
   * - ``stream``
     - bool
     - ``false``
     - Request streaming responses.
   * - ``max_completion_tokens``
     - int
     - *(unset)*
     - Upper bound on generated tokens. Must be ≥ 1 if set.
   * - ``presence_penalty``
     - float
     - *(unset)*
     - Presence penalty. Validated range −2.0–2.0.
   * - ``frequency_penalty``
     - float
     - *(unset)*
     - Frequency penalty. Validated range −2.0–2.0.
   * - ``effort``
     - string
     - *(unset)*
     - Reasoning effort for models that support it (e.g. ``low``, ``medium``, ``high``).

.. _agent-config:

[agent]
~~~~~~~

Maps the five named LLM variants to concrete routing groups or model ids. Variants are
ordered roughly by capability/cost:

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Slot
     - Default
     - Intended workload
   * - ``tiny``
     - *(unset)*
     - Trivial jobs: classification, yes/no checks, short rewrites.
   * - ``smol``
     - *(unset)*
     - Lightweight, low-context work above ``tiny`` scope.
   * - ``task``
     - *(unset)*
     - Routine workhorse: drafting, summarizing, structured extraction.
   * - ``slow``
     - *(unset)*
     - Harder reasoning, long-context comprehension.
   * - ``plan``
     - *(unset)*
     - Planning, multi-step strategy, quality-critical synthesis.

Resolution semantics: whenever a ``send_to`` candidate equals one of the five variant
names, it is looked up in this section. A **configured** slot resolves to its value; an
**unconfigured** slot yields nothing and resolution falls through to the next candidate
in the chain (call argument → capability default → ``llm.send_to``). Any other string is
used literally as a routing group name.

.. code-block:: toml

   [agent]
   tiny = "cheap"
   plan = "premium"

   [routing]   # groups referenced above must exist
   # ... deployments with group = "cheap" / "premium" ...

[embedding]
~~~~~~~~~~~

Default parameters for embedding requests.

.. list-table::
   :header-rows: 1
   :widths: 30 15 20 35

   * - Option
     - Type
     - Default
     - Description
   * - ``send_to``
     - string
     - *(unset)*
     - Default routing group for embedding requests.
   * - ``no_cache``
     - bool
     - *(unset)*
     - Disable response caching for embeddings.
   * - ``ndim``
     - int
     - *(unset)*
     - Dimensionality of output embedding vectors.
   * - ``max_batch_emb_size``
     - int
     - *(unset)*
     - Maximum texts per embedding API call; larger batches are split and fanned out in
       parallel. Unset means no chunking (the runtime falls back to batches of 10).

[reranker]
~~~~~~~~~~

Default parameters for reranking requests.

.. list-table::
   :header-rows: 1
   :widths: 30 15 20 35

   * - Option
     - Type
     - Default
     - Description
   * - ``send_to``
     - string
     - *(unset)*
     - Default routing group for reranker requests.
   * - ``no_cache``
     - bool
     - *(unset)*
     - Disable response caching for reranking.

[routing]
~~~~~~~~~

Providers, deployments, caching, and retry behavior for all model traffic.

**Providers** — upstream API endpoints:

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Field
     - Type
     - Description
   * - ``ptype``
     - string
     - One of ``OpenAI`` (official OpenAI; ``key`` may fall back to the
       ``OPENAI_API_KEY`` environment variable; ``name``/``base_url`` ignored),
       ``OpenAICompatible`` (any OpenAI-compatible endpoint; requires ``name``, ``key``
       and ``base_url``), or ``Dummy`` (makes no real HTTP calls; everything ignored —
       useful for tests).
   * - ``name``
     - string
     - Short identifier used in deployment ids (required for ``OpenAICompatible``).
   * - ``key``
     - string
     - API key; stored as a secret and redacted in logs/debug output.
   * - ``base_url``
     - string
     - Endpoint base URL; must be a valid URL (required for ``OpenAICompatible``).

**Deployments** — routable models bound to a group. Three independent lists exist:
``completion_deployments`` (chat/completion models), ``embedding_deployments``, and
``reranker_deployments``. All share the same schema:

.. list-table::
   :header-rows: 1
   :widths: 20 20 60

   * - Field
     - Type
     - Description
   * - ``id``
     - string
     - Deployment id, conventionally ``"<provider-name>/<model-name>"``.
   * - ``group``
     - string
     - Route group name that ``send_to`` refers to.
   * - ``tpm``
     - int
     - Optional tokens-per-minute quota.
   * - ``rpm``
     - int
     - Optional requests-per-minute quota.

**Cache and retries:**

.. list-table::
   :header-rows: 1
   :widths: 32 15 22 31

   * - Option
     - Type
     - Default
     - Description
   * - ``cache_database_path``
     - path
     - *(unset)*
     - SQLite cache location. Caching is enabled when set; omit to disable.
   * - ``retry_max_retries``
     - int
     - *(unset)*
     - Retry attempts for transient network failures. Unset disables retries.
   * - ``retry_initial_backoff_ms``
     - int
     - ``1000``
     - Backoff before the first retry.
   * - ``retry_max_backoff_ms``
     - int
     - ``30000``
     - Maximum backoff duration.
   * - ``retry_backoff_multiplier``
     - float
     - ``2.0``
     - Exponential backoff multiplier.

Example:

.. code-block:: toml

   [routing]
   cache_database_path = ".fabricatio.cache.db"
   retry_max_retries = 3

   providers = [
       { ptype = "OpenAICompatible", key = "sk-...", name = "mm", base_url = "https://api.example.com/v1/" }
   ]
   completion_deployments = [
       { id = "mm/gpt-4o-mini", group = "base", tpm = 100_000, rpm = 1000 }
   ]
   embedding_deployments = [
       { id = "mm/text-embedding-3-small", group = "embed", tpm = 100_000, rpm = 1000 }
   ]
   reranker_deployments = []

[template_manager]
~~~~~~~~~~~~~~~~~~

How templates are discovered and loaded.

.. list-table::
   :header-rows: 1
   :widths: 28 15 30 27

   * - Option
     - Type
     - Default
     - Description
   * - ``template_stores``
     - list of paths
     - ``["templates", "<ROAMING>/fabricatio/templates"]``
     - Directories scanned for templates; earlier entries win on filename conflicts.
   * - ``active_loading``
     - bool
     - ``false``
     - Enable active (eager) template loading.
   * - ``template_suffix``
     - string
     - ``"hbs"``
     - File extension treated as a template.

.. _configuration-core-templates:

[templates]
~~~~~~~~~~~

Template names used by core capabilities. Every entry defaults to its
``built-in/<name>`` variant:

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Option
     - Default
   * - ``mapping_template``
     - ``built-in/mapping``
   * - ``task_briefing_template``
     - ``built-in/task_briefing``
   * - ``dependencies_template``
     - ``built-in/dependencies``
   * - ``make_choice_template``
     - ``built-in/make_choice``
   * - ``make_enum_choice_template``
     - ``built-in/make_enum_choice``
   * - ``make_judgment_template``
     - ``built-in/make_judgment``
   * - ``code_string_template``
     - ``built-in/code_string``
   * - ``code_snippet_template``
     - ``built-in/code_snippet``
   * - ``generic_string_template``
     - ``built-in/generic_string``
   * - ``co_validation_template``
     - ``built-in/co_validation``
   * - ``liststr_template``
     - ``built-in/liststr``
   * - ``pathstr_template``
     - ``built-in/pathstr``
   * - ``create_json_obj_template``
     - ``built-in/create_json_obj``

[general]
~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 15 15 40

   * - Option
     - Type
     - Default
     - Description
   * - ``use_json_repair``
     - bool
     - ``true``
     - Automatically repair malformed JSON in LLM responses.

[emitter]
~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 30 15 15 40

   * - Option
     - Type
     - Default
     - Description
   * - ``delimiter``
     - string
     - ``"::"``
     - Delimiter used to split event names into segments.

.. _extension-config:

Extension Package Configuration
-------------------------------

Subpackages ship their own settings through the extension store: each package defines a
config dataclass/model and loads it with ``CONFIG.load("<ext_key>", <Class>)`` from
``fabricatio_core``. Values for ``ext_key`` come from the ``ext`` map of the same config
chain described above, so every package can be configured from all three source types:

.. code-block:: toml

   # fabricatio.toml
   [ext.comfyui]
   base_url = "http://127.0.0.1:8188"
   timeout = 600.0

.. code-block:: toml

   # pyproject.toml — equivalent form
   [tool.fabricatio.ext.comfyui]
   base_url = "http://127.0.0.1:8188"
   timeout = 600.0

.. code-block:: ini

   # environment — equivalent form
   FABRICATIO_EXT__COMFYUI__BASE_URL=http://127.0.0.1:8188
   FABRICATIO_EXT__COMFYUI__TIMEOUT=600

Extension tables **must** be nested under ``[ext.<ext_key>]`` (or the pyproject /
environment equivalent); a table placed directly at the top level of the TOML file is not
read by the loader.

At runtime the loader passes the stored mapping to the package's config class as keyword
arguments: fields named in the mapping take the configured value, everything else keeps
its in-code default. When the section is missing entirely, the loader instantiates the
class with pure defaults. Access the resolved singleton from Python:

.. code-block:: python

   from fabricatio_comfyui.config import comfyui_config

   print(comfyui_config.timeout)

Package Index
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 34 18 48

   * - Package
     - ``ext`` key
     - Runtime singleton
   * - `fabricatio-agent <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-agent>`_
     - ``agent``
     - ``fabricatio_agent.config.agent_config``
   * - `fabricatio-anki <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-anki>`_
     - ``anki``
     - ``fabricatio_anki.config.anki_config``
   * - `fabricatio-capabilities <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-capabilities>`_
     - ``capabilities``
     - ``fabricatio_capabilities.config.capabilities_config``
   * - `fabricatio-capable <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-capable>`_
     - ``capable``
     - ``fabricatio_capable.config.capable_config``
   * - `fabricatio-character <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-character>`_
     - ``character``
     - ``fabricatio_character.config.character_config``
   * - `fabricatio-checkpoint <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-checkpoint>`_
     - ``checkpoint``
     - ``fabricatio_checkpoint.config.checkpoint_config``
   * - `fabricatio-comfyui <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-comfyui>`_
     - ``comfyui``
     - ``fabricatio_comfyui.config.comfyui_config``
   * - `fabricatio-diff <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-diff>`_
     - ``diff``
     - ``fabricatio_diff.config.diff_config``
   * - `fabricatio-digest <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-digest>`_
     - ``digest``
     - ``fabricatio_digest.config.digest_config``
   * - `fabricatio-improve <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-improve>`_
     - ``improve``
     - ``fabricatio_improve.config.improve_config``
   * - `fabricatio-lancedb <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-lancedb>`_
     - ``lancedb``
     - ``fabricatio_lancedb.config.lancedb_config``
   * - `fabricatio-locale <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-locale>`_
     - ``locale``
     - ``fabricatio_locale.config.locale_config``
   * - `fabricatio-memory <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-memory>`_
     - ``memory``
     - ``fabricatio_memory.config.memory_config``
   * - `fabricatio-milvus <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-milvus>`_
     - ``milvus``
     - ``fabricatio_milvus.config.milvus_config``
   * - `fabricatio-mock <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-mock>`_
     - ``mock``
     - ``fabricatio_mock.config.mock_config``
   * - `fabricatio-novel <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-novel>`_
     - ``novel``
     - ``fabricatio_novel.config.novel_config``
   * - `fabricatio-plot <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-plot>`_
     - ``plot``
     - ``fabricatio_plot.config.plot_config``
   * - `fabricatio-question <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-question>`_
     - ``question``
     - ``fabricatio_question.config.question_config``
   * - `fabricatio-rag <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-rag>`_
     - ``rag``
     - ``fabricatio_rag.config.rag_config``
   * - `fabricatio-rule <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-rule>`_
     - ``rule``
     - ``fabricatio_rule.config.rule_config``
   * - `fabricatio-sandbox <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-sandbox>`_
     - ``sandbox``
     - ``fabricatio_sandbox.config.sandbox_config``
   * - `fabricatio-skill <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-skill>`_
     - ``skill``
     - ``fabricatio_skill.config.skill_config``
   * - `fabricatio-tagging <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-tagging>`_
     - ``tagging``
     - ``fabricatio_tagging.config.tagging_config``
   * - `fabricatio-team <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-team>`_
     - ``team``
     - ``fabricatio_team.config.team_config``
   * - `fabricatio-tei <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-tei>`_
     - ``tei``
     - ``fabricatio_tei.config.tei_config``
   * - `fabricatio-thinking <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-thinking>`_
     - ``thinking``
     - ``fabricatio_thinking.config.thinking_config``
   * - `fabricatio-tool <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-tool>`_
     - ``tool``
     - ``fabricatio_tool.config.tool_config``
   * - `fabricatio-translate <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-translate>`_
     - ``translate``
     - ``fabricatio_translate.config.translate_config``
   * - `fabricatio-typst <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-typst>`_
     - ``typst``
     - ``fabricatio_typst.config.typst_config``
   * - `fabricatio-webui <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-webui>`_
     - ``webui``
     - ``fabricatio_webui.config.webui_config``
   * - `fabricatio-workspace <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-workspace>`_
     - ``workspace``
     - ``fabricatio_workspace.config.workspace_config``
   * - `fabricatio-yue <https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-yue>`_
     - ``yue``
     - ``fabricatio_yue.config.yue_config``


Package Reference
~~~~~~~~~~~~~~~~~

Details for every extension package. Types and defaults are transcribed from each
package's ``config.py``; template-name options accept any name resolvable by the
template manager (see :ref:`[templates] section <configuration-core-templates>`).

fabricatio-agent
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 12 25 33

   * - Option
     - Type
     - Default
     - Description
   * - ``memory``
     - bool
     - ``false``
     - Whether to use memory.
   * - ``sequential_thinking``
     - bool
     - ``false``
     - Whether to think sequentially.
   * - ``check_capable``
     - bool
     - ``false``
     - Whether to check if the agent is capable of performing the task.
   * - ``fulfill_prompt_template``
     - string
     - ``built-in/fulfill_prompt``
     - The prompt template to use for fulfill.

fabricatio-anki
^^^^^^^^^^^^^^^

Template names used in the Anki card/model/deck generation stages.

.. list-table::
   :header-rows: 1
   :widths: 55 20 25

   * - Option
     - Type
     - Default
   * - ``generate_anki_card_front_side_template``
     - string
     - ``built-in/generate_anki_card_front_side``
   * - ``generate_anki_card_back_side_template``
     - string
     - ``built-in/generate_anki_card_back_side``
   * - ``generate_anki_card_template_template``
     - string
     - ``built-in/generate_anki_card_template``
   * - ``generate_anki_model_name_template``
     - string
     - ``built-in/generate_anki_model_name``
   * - ``generate_anki_card_template_generation_requirements_template``
     - string
     - ``built-in/generate_anki_card_template_generation_requirements``
   * - ``generate_anki_deck_metadata_template``
     - string
     - ``built-in/generate_anki_deck_metadata``
   * - ``generate_anki_model_generation_requirements_template``
     - string
     - ``built-in/generate_anki_model_generation_requirements``
   * - ``topic_analysis_assemble_template``
     - string
     - ``built-in/topic_analysis_assemble``
   * - ``generate_topic_analysis_template``
     - string
     - ``built-in/generate_topic_analysis``

Incorrect template names make the corresponding Anki object generation fail.

fabricatio-capabilities
^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 45 12 30 13

   * - Option
     - Type
     - Default
     - Used to
   * - ``extract_template``
     - string
     - ``built-in/extract``
     - extract a model from a string
   * - ``as_prompt_template``
     - string
     - ``built-in/as_prompt``
     - convert a string to a prompt
   * - ``dispatch_task_template``
     - string
     - ``built-in/dispatch_task``
     - dispatch a task
   * - ``rate_fine_grind_template``
     - string
     - ``built-in/rate_fine_grind``
     - rate fine grind
   * - ``draft_rating_manual_template``
     - string
     - ``built-in/draft_rating_manual``
     - draft a rating manual
   * - ``draft_rating_criteria_template``
     - string
     - ``built-in/draft_rating_criteria``
     - draft rating criteria
   * - ``extract_reasons_from_examples_template``
     - string
     - ``built-in/extract_reasons_from_examples``
     - extract reasons from examples
   * - ``extract_criteria_from_reasons_template``
     - string
     - ``built-in/extract_criteria_from_reasons``
     - extract criteria from reasons
   * - ``draft_rating_weights_klee_template``
     - string
     - ``built-in/draft_rating_weights_klee``
     - draft rating weights with Klee method
   * - ``order_string_template``
     - string
     - ``built-in/order_string``
     - order string output
   * - ``order_briefed_template``
     - string
     - ``built-in/order_briefed``
     - order briefed output

fabricatio-capable
^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 12 25 33

   * - Option
     - Type
     - Default
     - Description
   * - ``capable_template``
     - string
     - ``built-in/capable``
     - Template for checking whether a capability is capable of fulfilling a request.

fabricatio-character
^^^^^^^^^^^^^^^^^^^^

Templates (all default to their ``built-in/<name>`` variant):

``render_character_card_template``, ``mind_system_prompt_template``,
``mind_threat_analysis_template``, ``mind_fulfill_analysis_template``,
``mind_bias_judgment_template``, ``mind_impact_analysis_template``,
``mind_diamonds_template`` (default ``built-in/mind_diamonds_analysis``),
``mind_suffering_template`` (default ``built-in/mind_suffering_analysis``),
``mind_style_extraction_template`` (default ``built-in/mind_style_extraction``).

Thresholds:

.. list-table::
   :header-rows: 1
   :widths: 42 12 15 31

   * - Option
     - Type
     - Default
     - Description
   * - ``mind_personality_high``
     - float
     - ``70.0``
     - BigFive score above this counts as a "high" trait.
   * - ``mind_personality_low``
     - float
     - ``30.0``
     - BigFive score below this counts as a "low" trait.
   * - ``mind_emotion_intensity_high``
     - float
     - ``70.0``
     - Emotion intensity above this triggers high-arousal behavior.
   * - ``mind_emotion_intensity_mid``
     - float
     - ``40.0``
     - Emotion intensity above this triggers mild emotional coloring.
   * - ``mind_satisfaction_threshold``
     - int
     - ``3``
     - Accumulated positive events needed to rise one Maslow level.
   * - ``mind_cbt_confidence_threshold``
     - float
     - ``70.0``
     - If the rule filter's top distortion score exceeds this, its result is used directly instead of a full LLM call.
   * - ``mind_suffering_intensity_threshold``
     - float
     - ``80.0``
     - Emotion intensity above this triggers suffering creation.

Age brackets — ``(upper_bound_exclusive, shift_scale)`` pairs applied to personality
drift, default ``((12, 3.0), (18, 1.5), (25, 0.5), (999, 0.2))``.

Psychology knowledge tables (defaults are large literals; see
``packages/fabricatio-character/python/fabricatio_character/config.py``):

* ``mind_need_focus`` — Maslow level → behavioral description for prompt injection.
* ``mind_bias_examples`` — cognitive distortion → example internal monologue.
* ``mind_personality_rules`` — personality flag → behavioral description.
* ``mind_emotion_somatic_map`` — emotion keyword → high/low-intensity somatic states.
* ``mind_diamonds_distortion_boost`` — DIAMONDS situation dimension → distortion score boosts.

fabricatio-checkpoint
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 12 28 32

   * - Option
     - Type
     - Default
     - Description
   * - ``checkpoint_dir``
     - path
     - ``~/.fabricatio-checkpoint``
     - Directory to store checkpoints (a.k.a. the shadow repositories).
   * - ``cache_size``
     - int
     - ``100``
     - Maximum number of checkpoints to keep in memory.

fabricatio-comfyui
^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 12 30 30

   * - Option
     - Type
     - Default
     - Description
   * - ``base_url``
     - string
     - ``http://127.0.0.1:8188``
     - Base URL of the ComfyUI server.
   * - ``timeout``
     - float
     - ``300.0``
     - Default timeout in seconds for API requests.

fabricatio-diff
^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 38 12 22 28

   * - Option
     - Type
     - Default
     - Description
   * - ``match_precision``
     - float
     - ``1.0``
     - Precision threshold for matching.
   * - ``diff_template``
     - string
     - ``built-in/diff``
     - Template for diff output.
   * - ``hashline_diff_template``
     - string
     - ``built-in/hashline_diff``
     - Template for the LLM-driven hashline edit loop (self-correcting).
   * - ``hashline_judge_template``
     - string
     - ``built-in/hashline_judge``
     - Template for the YES/NO satisfaction judge inside the hashline edit loop.
   * - ``hashline_diff_max_iterations``
     - int
     - ``5``
     - Maximum LLM iterations for the hashline edit loop before giving up.

fabricatio-digest
^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 12 35 13

   * - Option
     - Type
     - Default
     - Description
   * - ``digest_template``
     - string
     - ``built-in/digest``
     - Template name for digest.
   * - ``task_list_explain_template``
     - string
     - ``built-in/task_list_explain``
     - Template name for task list explain.

fabricatio-improve
^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 12 32 16

   * - Option
     - Type
     - Default
     - Used to
   * - ``review_string_template``
     - string
     - ``built-in/review_string``
     - review a string
   * - ``fix_troubled_string_template``
     - string
     - ``built-in/fix_troubled_string``
     - fix a troubled string
   * - ``fix_troubled_obj_template``
     - string
     - ``built-in/fix_troubled_obj``
     - fix a troubled object

fabricatio-lancedb
^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 12 25 33

   * - Option
     - Type
     - Default
     - Description
   * - ``database_uri``
     - string
     - ``./lance.db``
     - LanceDB database URI.
   * - ``default_table_name``
     - string
     - ``default``
     - Table created/used when none is specified.

fabricatio-locale
^^^^^^^^^^^^^^^^^

The schema currently defines no options and is reserved for future use.

fabricatio-memory
^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 32 12 26 30

   * - Option
     - Type
     - Default
     - Description
   * - ``memory_record_template``
     - string
     - ``built-in/memory_record``
     - Template for recording memory.
   * - ``memory_recall_template``
     - string
     - ``built-in/memory_recall``
     - Template for recalling memory.
   * - ``sremember_template``
     - string
     - ``built-in/sremember``
     - Template for selective remembering.
   * - ``memory_store_root``
     - path
     - ``~/.fabricatio-memory``
     - Root directory for the memory store.
   * - ``writer_buffer_size``
     - int
     - ``50000000``
     - Buffer size for the memory store writer, in bytes.
   * - ``cache_size``
     - int
     - ``10``
     - Cache size for the memory store.

fabricatio-milvus
^^^^^^^^^^^^^^^^^

All options optional; unset values fall back to Milvus client defaults.

.. list-table::
   :header-rows: 1
   :widths: 26 14 15 45

   * - Option
     - Type
     - Default
     - Description
   * - ``milvus_uri``
     - string
     - *(unset)*
     - The URI of the Milvus server.
   * - ``milvus_timeout``
     - float
     - *(unset)*
     - The timeout of the Milvus server in seconds.
   * - ``milvus_token``
     - string
     - *(unset)*
     - The token for Milvus authentication.
   * - ``milvus_dimensions``
     - int
     - *(unset)*
     - The dimensions for Milvus vectors.

fabricatio-mock
^^^^^^^^^^^^^^^

The schema currently defines no options and is reserved for future use.

fabricatio-novel
^^^^^^^^^^^^^^^^

Template names for the novel overhaul pipeline (metadata extraction, planning,
prose writing, XHTML rendering, setting bible, writing style, character spans).
All default to their ``built-in/<name>`` variant:

``novel_metadata_requirement_template``, ``chapter_plan_template``,
``story_plan_template``, ``scene_plan_template``, ``scene_requirement_template``,
``render_chapter_xhtml_template``, ``setting_bible_characters_template``,
``setting_bible_background_template``, ``setting_bible_context_template``,
``setting_bible_export_template``, ``writing_style_as_prompt_template``,
``enriched_as_prompt_template``, ``novel_character_span_template``,
``chapter_character_span_template``, ``story_character_span_template``.

fabricatio-plot
^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 34 12 22 32

   * - Option
     - Type
     - Default
     - Description
   * - ``generate_header_template``
     - string
     - ``built-in/generate_header``
     - Template for generating header.
   * - ``generate_csv_data_template``
     - string
     - ``built-in/generate_csv_data``
     - Template for generating CSV data.
   * - ``csv_sep``
     - string
     - ``,``
     - Separator for CSV files.
   * - ``csv_codeblock_lang``
     - string
     - ``csv``
     - Language annotation for CSV code blocks.

fabricatio-question
^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 40 12 36 12

   * - Option
     - Type
     - Default
     - For
   * - ``selection_template``
     - string
     - ``built-in/selection``
     - selection questions
   * - ``selection_display_template``
     - string
     - ``built-in/selection_display``
     - selection display

fabricatio-rag
^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 34 12 24 30

   * - Option
     - Type
     - Default
     - Description
   * - ``refined_query_template``
     - string
     - ``built-in/refined_query``
     - Refine a query before retrieval.
   * - ``precise_chunk_template``
     - string
     - ``built-in/precise_chunk``
     - —
   * - ``enrich_qa_template``
     - string
     - ``built-in/enrich_qa``
     - Generate question-answer pairs from text chunks.
   * - ``mini_chunk_size``
     - int
     - ``128``
     - —

fabricatio-rule
^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 48 12 30 10

   * - Option
     - Type
     - Default
     - For
   * - ``ruleset_requirement_breakdown_template``
     - string
     - ``built-in/ruleset_requirement_breakdown``
     - breakdown a ruleset requirement
   * - ``rule_requirement_template``
     - string
     - ``built-in/rule_requirement``
     - generate a rule requirement
   * - ``check_string_template``
     - string
     - ``built-in/check_string``
     - check a string

fabricatio-sandbox
^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 28 16 22 34

   * - Option
     - Type
     - Default
     - Description
   * - ``sandbox_template``
     - string
     - ``built-in/sandbox``
     - Template name for LLM sandbox prompts.
   * - ``mounts``
     - map
     - *(empty)*
     - Default mount mapping ``{"/virtual": "/real/path", ...}``.

fabricatio-skill
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 32 14 32 22

   * - Option
     - Type
     - Default
     - Description
   * - ``select_skills_template``
     - string
     - ``built-in/select_skills``
     - LLM prompt selecting relevant skills from a question.
   * - ``distill_skills_template``
     - string
     - ``built-in/distill_skills``
     - LLM prompt distilling skill content to its essence.
   * - ``default_skill_dirs``
     - list
     - ``["skills", "extra/skills"]``
     - Directories scanned for skill files.

fabricatio-tagging
^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 12 25 33

   * - Option
     - Type
     - Default
     - Description
   * - ``tagging_template``
     - string
     - ``built-in/tagging``
     - The template to use for tagging.

fabricatio-team
^^^^^^^^^^^^^^^

The schema currently defines no options and is reserved for future use.

fabricatio-tei
^^^^^^^^^^^^^^

The schema currently defines no options and is reserved for future use.

fabricatio-thinking
^^^^^^^^^^^^^^^^^^^

The schema currently defines no options and is reserved for future use.

fabricatio-tool
^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 34 16 20 30

   * - Option
     - Type
     - Default
     - Description
   * - ``draft_tool_usage_code_template``
     - string
     - ``built-in/draft_tool_usage_code``
     - Draft tool usage code template.
   * - ``check_modules``
     - CheckConfigModel_
     - targets empty, mode whitelist
     - Modules forbidden/allowed to be imported.
   * - ``check_imports``
     - CheckConfigModel_
     - targets ``{"math"}``, mode whitelist
     - Imports forbidden/allowed to be used.
   * - ``check_calls``
     - CheckConfigModel_
     - builtins plus ``pathlib.Path``, ``print``, ``len``; mode whitelist
     - Calls forbidden/allowed to be used.
   * - ``mcp_servers``
     - map of ServiceConfig_
     - *(empty)*
     - MCP servers allowed to be used.
   * - ``confirm_on_ops``
     - bool
     - ``true``
     - Confirm operations before executing them.
   * - ``logging_on_ops``
     - bool
     - ``true``
     - Log operations before executing them.
   * - ``error_key``
     - string
     - ``__error__``
     - Key used for error reporting.

``CheckConfigModel`` fields: ``targets`` (set of strings) and ``mode``
(``"whitelist"`` or ``"blacklist"``, default ``"whitelist"``).

``ServiceConfig`` fields: ``type`` (``"stdio"``, ``"sse"``, ``"stream"`` or
``"worker"``, default ``"stdio"``), ``command`` + ``args`` + ``env`` for stdio
services, ``url`` for sse/stream/worker services.

.. _CheckConfigModel: https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-tool
.. _ServiceConfig: https://github.com/Whth/fabricatio/tree/master/packages/fabricatio-tool

fabricatio-translate
^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 12 25 33

   * - Option
     - Type
     - Default
     - Description
   * - ``translate_template``
     - string
     - ``built-in/translate``
     - The template to use for translation.

fabricatio-typst
^^^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 42 12 28 18

   * - Option
     - Type
     - Default
     - Description
   * - ``chap_summary_template``
     - string
     - ``built-in/chap_summary``
     - Generate a chapter summary.
   * - ``research_content_summary_template``
     - string
     - ``built-in/research_content_summary``
     - Summarize research content.
   * - ``paragraph_sep``
     - string
     - ``// - - -``
     - Separator inserted between paragraphs.
   * - ``article_wrapper``
     - string
     - ``// =-=-=-=-=-=-=-=-=-=``
     - Wrapper drawn around an article.
   * - ``extract_essence_template``
     - string
     - ``built-in/extract_essence``
     - Extract the essence of a text.
   * - ``generate_outline_template``
     - string
     - ``built-in/generate_outline``
     - Generate an outline.

fabricatio-webui
^^^^^^^^^^^^^^^^

Server runtime settings for the board editor and execution service, honored by the
``fc-webui`` CLI.

.. list-table::
   :header-rows: 1
   :widths: 26 14 34 26

   * - Option
     - Type
     - Default
     - Description
   * - ``addr``
     - string
     - ``127.0.0.1:9846``
     - Bind address for the HTTP/WS server.
   * - ``frontend_dir``
     - string
     - *(empty)*
     - Directory of a custom frontend build; empty uses the bundled SPA.
   * - ``allowed_origins``
     - list
     - ``["http://localhost:*", "http://127.0.0.1:*"]``
     - CORS origin patterns; empty list is permissive.
   * - ``queue_max``
     - int
     - ``64``
     - Max queued executions before submit raises.
   * - ``history_max``
     - int
     - ``256``
     - Max finished executions kept in history.
   * - ``persist_workflows``
     - bool
     - ``true``
     - ``false`` keeps boards in memory only and never writes ``workflows.json``.

fabricatio-workspace
^^^^^^^^^^^^^^^^^^^^

The schema currently defines no options and is reserved for future use.

fabricatio-yue
^^^^^^^^^^^^^^

.. list-table::
   :header-rows: 1
   :widths: 30 18 30 22

   * - Option
     - Type
     - Default
     - Description
   * - ``segment_types``
     - list
     - verse, chorus, bridge, intro, outro, solo, beat, end
     - Valid segment types for music composition.
   * - ``genre``
     - map
     - (bundled tag catalog)
     - Genre categories mapped to lists of specific genres; default loads from
       the package's ``top_200_tags.json``.
   * - ``lyricize_template``
     - string
     - ``built-in/lyricize``
     - Lyric generation template.
   * - ``select_genre_template``
     - string
     - ``built-in/select_genre``
     - Genre selection template.
   * - ``song_save_template``
     - string
     - ``built-in/song_save``
     - Song saving template.

Real-World Examples
-------------------

Single OpenAI-compatible provider
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

   [debug]
   log_level = "INFO"

   [llm]
   send_to = "openai"
   max_completion_tokens = 16000
   temperature = 0.7

   [routing]
   providers = [
       { ptype = "OpenAICompatible", key = "sk-proj-xxx", name = "openai",
         base_url = "https://api.openai.com/v1/" }
   ]
   completion_deployments = [
       { id = "openai/gpt-4o", group = "openai", tpm = 100_000, rpm = 500 },
       { id = "openai/gpt-4o-mini", group = "openai", tpm = 200_000, rpm = 2000 }
   ]

Multi-provider fallback with model tiers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

   [llm]
   send_to = "primary"

   [agent]
   tiny = "cheap"
   plan = "premium"

   [routing]
   providers = [
       { ptype = "OpenAICompatible", key = "sk-primary", name = "primary",
         base_url = "https://api.openai.com/v1/" },
       { ptype = "OpenAICompatible", key = "sk-fallback", name = "fallback",
         base_url = "https://api.deepseek.com/v1/" }
   ]
   completion_deployments = [
       { id = "primary/gpt-4o", group = "premium", tpm = 100_000, rpm = 500 },
       { id = "primary/gpt-4o-mini", group = "primary", tpm = 200_000, rpm = 2000 },
       { id = "fallback/deepseek-chat", group = "fallback", tpm = 100_000, rpm = 1000 }
   ]
   retry_max_retries = 3

Usage:

.. code-block:: python

   # Uses [llm] send_to -> "primary"
   response = await self.aask("Complex task")

   # Explicitly pick a group
   response = await self.aask("Cost-sensitive task", send_to="fallback")

   # Variant slots: capabilities that request the "tiny"/"plan" variants resolve
   # through [agent]; unconfigured variants fall through to [llm] send_to.

Local models
~~~~~~~~~~~~

.. code-block:: toml

   [llm]
   send_to = "local"
   stream = false

   [routing]
   providers = [
       { ptype = "OpenAICompatible", key = "not-needed", name = "ollama",
         base_url = "http://localhost:11434/v1/" }
   ]
   completion_deployments = [
       { id = "ollama/llama3", group = "local" }
   ]

Testing without network
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

   [routing]
   providers = [
       { ptype = "Dummy" }
   ]
   completion_deployments = [
       { id = "dummy/mock-model", group = "mock" }
   ]

The ``Dummy`` provider makes no real HTTP calls; combine it with the mock package for
deterministic tests.

Troubleshooting
---------------

**Configuration not being loaded?**

- Check the file is named exactly ``fabricatio.toml`` and sits in the working
  directory where the process starts.
- In ``pyproject.toml`` the table must be under ``[tool.fabricatio]``.
- Enable debug logging: ``FABRICATIO_DEBUG__LOG_LEVEL=DEBUG``.
- Validate TOML syntax (an invalid file fails config load at startup).

**Environment variables not working?**

- Use double underscores: ``FABRICATIO_LLM__TEMPERATURE`` (not single).
- Remember ``./.env`` overrides real environment variables of the same name.
- Complex values (provider/deployment lists) are awkward through env vars —
  put them in a TOML file instead.

**Extension package config not applying?**

- Tables must live under ``[ext.<key>]`` / ``[tool.fabricatio.ext.<key>]`` /
  ``FABRICATIO_EXT__<KEY>__<FIELD>`` — a top-level ``[<key>]`` table is ignored.
- Field names must match the package's config class exactly (they become
  keyword arguments); unknown names raise type errors at import time.

**"send_to is not specified"?**

- Set ``[llm] send_to`` (or pass ``send_to=...`` per call). If you set it to a
  variant name such as ``tiny`` or ``plan``, configure the matching slot under
  ``[agent]`` or resolution falls through.

**Provider authentication failures?**

- Verify the API key has no leading/trailing spaces.
- ``OpenAICompatible`` requires both ``name`` and ``base_url``; ``base_url``
  must include the version path (e.g. ``https://api.openai.com/v1/``).
- ``ptype`` accepts only ``OpenAI``, ``OpenAICompatible`` and ``Dummy``.

**Rate limit errors (429)?**

- Check TPM/RPM quotas on your deployments.
- Reduce request frequency, add fallback deployments in other groups, or enable
  caching via ``cache_database_path``.

**Cache database errors?**

- Ensure the directory exists and is writable.
- Delete the cache file to reset if corrupted.

**Model not found errors?**

- Deployment ids conventionally follow ``<provider-name>/<model-name>``; verify
  the model exists for that provider/account.
