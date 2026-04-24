Configuration Guide
==================

Fabricatio provides a flexible, multi-source configuration system with clear priority order. This guide covers all configuration options and their interactions.

.. contents::
   :local:
   :depth: 3

Quick Start Tutorial
-------------------

This section walks you through setting up Fabricatio for the first time.

Step 1: Install Fabricatio
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Install with full capabilities
    pip install fabricatio[full]

    # Or with uv
    uv add fabricatio[full]

Step 2: Create a Configuration File
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a ``fabricatio.toml`` in your project root:

.. code-block:: toml

    [debug]
    log_level = "INFO"

    [llm]
    send_to = "base"
    max_completion_tokens = 16000
    stream = false
    temperature = 1.0
    top_p = 1.0
    timeout = 120

    [routing]
    providers = [
        { ptype = "OpenAICompatible", key = "sk-your-api-key", name = "openai", base_url = "https://api.openai.com/v1/" }
    ]
    
    completion_deployments = [
        { id = "openai/gpt-4o-mini", group = 'base', tpm = 100_000, rpm = 1000 }
    ]
    
    cache_database_path = ".fabricatio.cache.db"

Step 3: Verify Your Setup
~~~~~~~~~~~~~~~~~~~~~~~~~

Create a simple test script:

.. code-block:: python

    from fabricatio import Role, Action, WorkFlow, Event, Task

    class TestAction(Action):
        output_key: str = "test_output"
        
        async def _execute(self, **_) -> str:
            return "Fabricatio is working!"

    role = Role().add_skill(
        Event.quick_instantiate("test"),
        WorkFlow(name="test", steps=(TestAction,))
    ).dispatch()

    result = Task(name="verify").delegate_blocking("test")
    print(result)  # Should print: "Fabricatio is working!"

Step 4: Configure Your First Agent
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here's a complete example using configuration:

.. code-block:: python

    from fabricatio import Role, Action, WorkFlow, Event, Task
    from fabricatio.capabilities import UseLLM

    class LLMGreetAction(Action, UseLLM):
        output_key: str = "greeting"
        
        async def _execute(self, name: str, **_) -> str:
            response = await self.aask(f"Say hello to {name} in one sentence")
            return response

    # Create role with custom LLM configuration
    role = Role(
        config={
            "llm": {"temperature": 0.7},
            "debug": {"log_level": "DEBUG"}
        }
    ).add_skill(
        Event.quick_instantiate("greet"),
        WorkFlow(name="greet", steps=(LLMGreetAction,))
    ).dispatch()

    # Run the task
    result = Task(name="hello").delegate_blocking("greet", name="World")
    print(result)

Configuration Sources & Priority
---------------------------------

Fabricatio loads configuration from multiple sources in the following priority order (highest to lowest):

.. code-block:: text

    1. Call Arguments (programmatic API)
           │
           ▼
    2. .env file in current directory
           │
           ▼
    3. Environment Variables
           │
           ▼
    4. ./fabricatio.toml
           │
           ▼
    5. ./pyproject.toml [tool.fabricatio]
           │
           ▼
    6. <ROAMING>/fabricatio/fabricatio.toml
           │
           ▼
    7. Built-in Defaults

This means you can override any configuration at runtime using environment variables or programmatically.

Configuration File Formats
--------------------------

fabricatio.toml
~~~~~~~~~~~~~~~

The primary configuration file format:

.. code-block:: toml

    [debug]
    log_level = "DEBUG"          # DEBUG, INFO, WARNING, ERROR

    [llm]
    send_to = "base"             # Default routing group
    max_completion_tokens = 32000
    stream = false
    temperature = 1.0
    top_p = 0.35
    timeout = 120                # seconds

    [routing]
    providers = [
        { ptype = "OpenAICompatible", key = "sk-...", name = "mm", base_url = "https://api.example.com/v1/" }
    ]
    
    completion_deployments = [
        { id = "mm/gpt-4o-mini", group = 'base', tpm = 100_000, rpm = 1000 }
    ]
    
    cache_database_path = "path/to/.cache.db"

pyproject.toml
~~~~~~~~~~~~~~

Configuration via ``[tool.fabricatio]`` table:

.. code-block:: toml

    [tool.fabricatio.debug]
    log_level = "DEBUG"

    [tool.fabricatio.llm]
    send_to = "base"
    max_completion_tokens = 32000
    stream = false
    temperature = 1.0
    top_p = 0.35

    [tool.fabricatio.routing]
    providers = [
        { ptype = "OpenAICompatible", key = "sk-...", name = "mm", base_url = "https://api.example.com/v1/" }
    ]

    completion_deployments = [
        { id = "mm/gpt-4o-mini", group = 'base', tpm = 100_000, rpm = 1000 }
    ]

Environment Variables / .env
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Prefix all config keys with ``FABRICATIO_`` and use double underscores for nesting:

.. code-block:: dotenv

    FABRICATIO_DEBUG__LOG_LEVEL=DEBUG
    FABRICATIO_LLM__SEND_TO=base
    FABRICATIO_LLM__MAX_COMPLETION_TOKENS=32000
    FABRICATIO_LLM__STREAM=false
    FABRICATIO_LLM__TEMPERATURE=1.0
    FABRICATIO_LLM__TOP_P=0.35

Configuration Sections
----------------------

[debug]
~~~~~~~

+------------------------+---------------------------+---------+
| Key                    | Description               | Default |
+========================+===========================+=========+
| ``log_level``          | Logging level             | ``INFO``|
+------------------------+---------------------------+---------+

[llm]
~~~~

+---------------------------+---------------------------+---------+
| Key                       | Description               | Default |
+===========================+===========================+=========+
| ``send_to``               | Default routing group     | ``base``|
+---------------------------+---------------------------+---------+
| ``max_completion_tokens`` | Max tokens in response    |``16000``|
+---------------------------+---------------------------+---------+
| ``stream``                | Enable streaming responses|``false``|
+---------------------------+---------------------------+---------+
| ``temperature``           | Sampling temperature      | ``1.0`` |
+---------------------------+---------------------------+---------+
| ``top_p``                | Nucleus sampling threshold | ``1.0`` |
+---------------------------+---------------------------+---------+
| ``timeout``              | Request timeout (seconds)  | ``120`` |
+---------------------------+---------------------------+---------+

[routing]
~~~~~~~~

Provider Configuration
^^^^^^^^^^^^^^^^^^^^^

Providers define LLM endpoints:

.. code-block:: python

    {
        "ptype": "OpenAICompatible",  # Provider type
        "key": "sk-...",               # API key
        "name": "mm",                  # Short name for routing
        "base_url": "https://api.example.com/v1/"  # Endpoint base
    }

Supported provider types:

- ``OpenAICompatible`` - OpenAI API compatible endpoints
- ``Anthropic`` - Anthropic API
- ``AzureOpenAI`` - Microsoft Azure OpenAI
- ``GoogleAI`` - Google AI (Gemini)
- ``Local`` - Local model endpoints

Deployment Configuration
^^^^^^^^^^^^^^^^^^^^^^^

Deployments define available models:

.. code-block:: python

    {
        "id": "mm/gpt-4o-mini",        # Full model ID (provider/name)
        "group": "base",               # Routing group
        "tpm": 100_000,                # Tokens per minute limit
        "rpm": 1000                    # Requests per minute limit
    }

Cache Configuration
^^^^^^^^^^^^^^^^^^

.. code-block:: toml

    [routing]
    cache_database_path = "path/to/.cache.db"  # SQLite cache location

Router Features
^^^^^^^^^^^^^^

The ``thryd`` crate provides:

- **TPM/RPM limiting**: Per-deployment rate limiting
- **Response caching**: SQLite-based request caching
- **Concurrent routing**: Thread-safe provider selection

Programmatic Configuration
--------------------------

Role-level Configuration
~~~~~~~~~~~~~~~~~~~~~~~~

Pass configuration directly to Roles:

.. code-block:: python

    from fabricatio import Role

    role = Role(
        name="my_agent",
        config={
            "llm": {"temperature": 0.7},
            "debug": {"log_level": "DEBUG"}
        }
    )

Action-level Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Override configuration per action call:

.. code-block:: python

    from fabricatio.capabilities import UseLLM

    class MyAction(Action, UseLLM):
        async def _execute(self, task_input, **kwargs):
            # Use custom temperature for this call
            response = await self.aask(
                "Explain quantum computing",
                temperature=0.3  # Override default
            )
            return response

aask() vs aask_structured()
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``aask()`` - Simple text responses:

.. code-block:: python

    response: str = await self.aask("What is Python?")

``aask_structured()`` - Typed responses with Pydantic:

.. code-block:: python

    from pydantic import BaseModel

    class CodeReview(BaseModel):
        issues: list[str]
        score: int
        suggestions: list[str]

    result: CodeReview = await self.aask_structured(
        "Review this code",
        response_format=CodeReview
    )

Real-World Configuration Examples
--------------------------------

Example 1: Single Provider with OpenAI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

    [debug]
    log_level = "INFO"

    [llm]
    send_to = "openai"
    max_completion_tokens = 16000
    temperature = 0.7

    [routing]
    providers = [
        { ptype = "OpenAICompatible", key = "sk-proj-xxxx", name = "openai", base_url = "https://api.openai.com/v1/" }
    ]
    
    completion_deployments = [
        { id = "openai/gpt-4o", group = 'openai', tpm = 100_000, rpm = 500 },
        { id = "openai/gpt-4o-mini", group = 'openai', tpm = 200_000, rpm = 2000 }
    ]

Example 2: Multi-Provider with Fallback
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

    [llm]
    send_to = "primary"

    [routing]
    providers = [
        { ptype = "OpenAICompatible", key = "sk-primary-xxx", name = "primary", base_url = "https://api.openai.com/v1/" },
        { ptype = "OpenAICompatible", key = "sk-fallback-xxx", name = "fallback", base_url = "https://api.deepseek.com/v1/" }
    ]
    
    completion_deployments = [
        { id = "primary/gpt-4o", group = 'primary', tpm = 100_000, rpm = 500 },
        { id = "primary/gpt-4o-mini", group = 'primary', tpm = 200_000, rpm = 2000 },
        { id = "fallback/deepseek-chat", group = 'fallback', tpm = 100_000, rpm = 1000 }
    ]

Usage:

.. code-block:: python

    # Uses primary group (default)
    response = await self.aask("Complex task")

    # Explicitly use fallback
    response = await self.aask("Cost-sensitive task", send_to="fallback")

Example 3: Anthropic with Claude
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

    [llm]
    send_to = "claude"
    max_completion_tokens = 32000
    temperature = 1.0

    [routing]
    providers = [
        { ptype = "Anthropic", key = "sk-ant-api03-xxx", name = "claude" }
    ]
    
    completion_deployments = [
        { id = "claude/claude-3-5-sonnet-latest", group = 'claude', tpm = 100_000, rpm = 1000 }
    ]

Example 4: Azure OpenAI
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

    [routing]
    providers = [
        { 
            ptype = "AzureOpenAI", 
            key = "your-azure-key", 
            name = "azure", 
            base_url = "https://your-resource.openai.azure.com/",
            api_version = "2024-02-01"
        }
    ]
    
    completion_deployments = [
        { id = "azure/gpt-4o", group = 'azure', tpm = 100_000, rpm = 500 }
    ]

Example 5: Local Model Setup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

    [llm]
    send_to = "local"
    timeout = 300  # Longer timeout for local models

    [routing]
    providers = [
        { ptype = "Local", key = "not-needed", name = "ollama", base_url = "http://localhost:11434/v1/" }
    ]
    
    completion_deployments = [
        { id = "ollama/llama3", group = 'local', tpm = 999_999_999, rpm = 999_999_999 }
    ]

Advanced: Multiple Provider Setup
---------------------------------

Load Balancing Across Providers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

    [routing]
    providers = [
        { ptype = "OpenAICompatible", key = "sk-primary", name = "openai", base_url = "https://api.openai.com/v1/" },
        { ptype = "OpenAICompatible", key = "sk-secondary", name = "azure", base_url = "https://example.azure.com/v1/" }
    ]
    
    completion_deployments = [
        { id = "openai/gpt-4o", group = 'premium', tpm = 100_000, rpm = 500 },
        { id = "azure/gpt-4o", group = 'premium', tpm = 200_000, rpm = 1000 }
    ]

Using Different Groups:

.. code-block:: python

    # Send to premium group
    response = await self.aask("Complex task", send_to="premium")

    # Send to base group (default)
    response = await self.aask("Simple task", send_to="base")

Environment-Specific Configs
----------------------------

Development (.env.local)
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: dotenv

    FABRICATIO_DEBUG__LOG_LEVEL=DEBUG
    FABRICATIO_LLM__SEND_TO=local
    FABRICATIO_ROUTING__CACHE_DATABASE_PATH=.cache.local.db

Staging (fabricatio.staging.toml)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create ``fabricatio.staging.toml``:

.. code-block:: toml

    [debug]
    log_level = "INFO"

    [llm]
    send_to = "staging"
    timeout = 90

    [routing]
    providers = [
        { ptype = "OpenAICompatible", key = "sk-staging-xxx", name = "staging", base_url = "https://api.staging.example.com/v1/" }
    ]
    
    completion_deployments = [
        { id = "staging/gpt-4o-mini", group = 'staging', tpm = 50_000, rpm = 500 }
    ]
    
    cache_database_path = "/var/cache/fabricatio/.cache.staging.db"

Production (fabricatio.toml)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

    [debug]
    log_level = "WARNING"

    [llm]
    send_to = "production"
    timeout = 60

    [routing]
    cache_database_path = "/var/cache/fabricatio/.cache.db"

Loading Environment-Specific Config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Fabricatio automatically loads ``fabricatio.toml`` from the current directory. To use environment-specific configurations:

.. code-block:: bash

    # Development
    cp fabricatio.dev.toml fabricatio.toml

    # Production
    cp fabricatio.prod.toml fabricatio.toml

Or use environment variables:

.. code-block:: bash

    export FABRICATIO_ROUTING__CACHE_DATABASE_PATH="/var/cache/fabricatio/.cache.db"
    export FABRICATIO_DEBUG__LOG_LEVEL="WARNING"

Template Discovery Configuration
--------------------------------

Fabricatio searches for templates in multiple locations:

.. code-block:: text

    Priority (high to low):
    1. ./templates/           (project working directory)
    2. <ROAMING>/fabricatio/templates/
    3. Built-in templates

Download templates:

.. code-block:: bash

    # Manual download
    curl -L https://github.com/Whth/fabricatio/releases/download/v0.19.1/templates.tar.gz | tar -xz

    # Using bundled CLI
    tdown download --verbose -o ./

Caching Configuration
---------------------

Fabricatio uses SQLite for request caching. Configure cache behavior:

.. code-block:: toml

    [routing]
    cache_database_path = "path/to/.cache.db"  # Custom cache location

Cache Environment Variables:

.. code-block:: bash

    FABRICATIO_ROUTING__CACHE_DATABASE_PATH=".fabricatio.cache.db"

Cache is automatically enabled when ``cache_database_path`` is configured. To disable caching, simply omit this configuration or set it to an empty path.

Troubleshooting
---------------

**Config not being loaded?**

- Check file location matches expected paths
- Verify ``[tool.fabricatio]`` section in pyproject.toml (not ``[tool.fabricatio.routing]``)
- Enable debug logging: ``FABRICATIO_DEBUG__LOG_LEVEL=DEBUG``
- Confirm the file is valid TOML syntax

**Environment variables not working?**

- Use double underscores: ``FABRICATIO_LLM__TEMPERATURE`` (not single)
- Verify .env file is in the current working directory
- Check for trailing whitespace in .env file
- Ensure no quotes around values (unless required)

**Provider authentication failures?**

- Verify API key is correct and has no leading/trailing spaces
- Check base_url includes trailing slash (/v1/)
- Ensure rate limits (TPM/RPM) are set appropriately
- For Azure, verify api_version is correct

**Rate limit errors (429)?**

- Check TPM/RPM limits in your deployment configuration
- Reduce request frequency or increase limits
- Enable caching to reduce API calls
- Consider adding fallback providers

**Request timeout errors?**

- Increase ``timeout`` value in [llm] section
- Check network connectivity to API endpoint
- For local models, increase timeout to 300+ seconds

**Structured output parsing errors?**

- Ensure response_format is a Pydantic BaseModel
- Check that your model supports structured output
- Verify temperature is set appropriately (lower values help)

**Cache database errors?**

- Ensure the cache directory exists and is writable
- Check disk space availability
- Delete the cache file to reset if corrupted

**Debug logging not showing?**

- Set ``log_level = "TRACE"`` for most verbose output
- Check that debug config is in the correct section
- Verify no other configuration is overriding it

**Model not found errors?**

- Verify deployment ID matches provider naming (provider/model-name)
- Check that the model is available in your account/region
- For local models, ensure the server is running

Common Configuration Patterns
-----------------------------

Pattern 1: Development with Local Caching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

    [debug]
    log_level = "DEBUG"

    [llm]
    send_to = "local"
    stream = false

    [routing]
    providers = [
        { ptype = "OpenAICompatible", key = "sk-dev", name = "dev", base_url = "https://api.openai.com/v1/" }
    ]
    
    completion_deployments = [
        { id = "dev/gpt-4o-mini", group = 'local', tpm = 999_999_999, rpm = 999_999_999 }
    ]
    
    cache_database_path = ".dev.cache.db"

Pattern 2: Production with Multiple Tiers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

    [debug]
    log_level = "WARNING"

    [llm]
    send_to = "premium"
    timeout = 60

    [routing]
    providers = [
        { ptype = "OpenAICompatible", key = "sk-prod", name = "openai", base_url = "https://api.openai.com/v1/" },
        { ptype = "OpenAICompatible", key = "sk-backup", name = "backup", base_url = "https://api.backup.com/v1/" }
    ]
    
    completion_deployments = [
        { id = "openai/gpt-4o", group = 'premium', tpm = 100_000, rpm = 500 },
        { id = "openai/gpt-4o-mini", group = 'standard', tpm = 200_000, rpm = 2000 },
        { id = "backup/gpt-4o-mini", group = 'backup', tpm = 50_000, rpm = 500 }
    ]
    
    cache_database_path = "/var/cache/fabricatio/.cache.db"

Pattern 3: Cost-Optimized Setup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: toml

    [llm]
    send_to = "budget"
    max_completion_tokens = 8000

    [routing]
    providers = [
        { ptype = "OpenAICompatible", key = "sk-budget", name = "deepseek", base_url = "https://api.deepseek.com/v1/" }
    ]
    
    completion_deployments = [
        { id = "deepseek/deepseek-chat", group = 'budget', tpm = 100_000, rpm = 1000 }
    ]
    
    cache_database_path = ".budget.cache.db"

Migration Guide
---------------

Migrating from v0.x to v1.x
~~~~~~~~~~~~~~~~~~~~~~~~~~~

The configuration format has been updated:

**Old format:**

.. code-block:: toml

    [fabricatio]
    log_level = "INFO"

**New format:**

.. code-block:: toml

    [debug]
    log_level = "INFO"

Key changes:

- ``[fabricatio]`` section renamed to specific sections (``[debug]``, ``[llm]``, ``[routing]``)
- Provider configuration uses inline TOML tables
- Environment variables now use double underscores for nesting

For more information, see the `full migration guide <https://fabricatio.readthedocs.io/en/latest/migration.html>`_.
