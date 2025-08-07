Configuration
=============

Fabricatio supports flexible configuration through multiple sources, with the following priority order:
`Call Arguments` > `./.env` > `Environment Variables` > `./fabricatio.toml` > `./pyproject.toml` > `<ROMANING>/fabricatio/fabricatio.toml` > `Builtin Defaults`.

Below is a unified view of the same configuration expressed in different formats:

Environment variables or dotenv file
------------------------------------

.. code-block:: dotenv

   FABRICATIO_LLM__API_ENDPOINT=https://api.openai.com
   FABRICATIO_LLM__API_KEY=your_openai_api_key
   FABRICATIO_LLM__TIMEOUT=300
   FABRICATIO_LLM__MAX_RETRIES=3
   FABRICATIO_LLM__MODEL=openai/gpt-3.5-turbo
   FABRICATIO_LLM__TEMPERATURE=1.0
   FABRICATIO_LLM__TOP_P=0.35
   FABRICATIO_LLM__GENERATION_COUNT=1
   FABRICATIO_LLM__STREAM=false
   FABRICATIO_LLM__MAX_TOKENS=8192
   FABRICATIO_DEBUG__LOG_LEVEL=INFO

`fabricatio.toml` file
----------------------

.. code-block:: toml

   [llm]
   api_endpoint = "https://api.openai.com"
   api_key = "your_openai_api_key"
   timeout = 300
   max_retries = 3
   model = "openai/gpt-3.5-turbo"
   temperature = 1.0
   top_p = 0.35
   generation_count = 1
   stream = false
   max_tokens = 8192

   [debug]
   log_level = "INFO"

`pyproject.toml` file
---------------------

.. code-block:: toml

   [tool.fabricatio.llm]
   api_endpoint = "https://api.openai.com"
   api_key = "your_openai_api_key"
   timeout = 300
   max_retries = 3
   model = "openai/gpt-3.5-turbo"
   temperature = 1.0
   top_p = 0.35
   generation_count = 1
   stream = false
   max_tokens = 8192

   [tool.fabricatio.debug]
   log_level = "INFO"

Configuration Options
---------------------

**LLM Settings:**

- ``api_endpoint``: The API endpoint for the LLM service
- ``api_key``: Your API key for authentication
- ``timeout``: Request timeout in seconds (default: 300)
- ``max_retries``: Maximum number of retry attempts (default: 3)
- ``model``: Model identifier (e.g., "openai/gpt-3.5-turbo")
- ``temperature``: Sampling temperature (0.0 to 2.0)
- ``top_p``: Nucleus sampling parameter
- ``generation_count``: Number of generations per request
- ``stream``: Enable streaming responses
- ``max_tokens``: Maximum tokens in response

**Debug Settings:**

- ``log_level``: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

Configuration Priority
----------------------

Configuration values are resolved in the following order (highest to lowest priority):

1. **Call Arguments** - Parameters passed directly to function calls
2. **./.env** - Environment file in the current working directory
3. **Environment Variables** - System environment variables with ``FABRICATIO_`` prefix
4. **./fabricatio.toml** - Configuration file in the current working directory
5. **./pyproject.toml** - Project configuration file (under ``[tool.fabricatio]``)
6. **<ROMANING>/fabricatio/fabricatio.toml** - User-specific configuration file
7. **Builtin Defaults** - Default values provided by the library