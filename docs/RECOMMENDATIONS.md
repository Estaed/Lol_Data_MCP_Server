# Codebase Improvement Recommendations for Lol_Data_MCP_Server

This document provides a detailed analysis of the Python files within the `src` directory, highlighting areas for improvement in terms of redundancy, clarity, efficiency, maintainability, error handling, modularity, and adherence to best practices. The recommendations are structured to be directly actionable.

---

## `src/core/config.py`

### General Observations
This module provides a robust configuration management system using Pydantic. However, there are minor areas for refinement related to redundancy and logging.

### Specific Recommendations

1.  **Consolidate `create_config_template` and `default_settings`:**
    *   **Issue:** These functions (`create_config_template` and `default_settings`) are currently part of `config.py` but are not directly used within the `Settings` class or its core loading mechanism. They appear to be utility functions for external use or testing.
    *   **Recommendation:** Move these functions to a dedicated `src/utils/config_utils.py` module if they are intended for external use (e.g., CLI tools for generating config files). If they are not used at all, consider removing them.
    *   **Action:**
        *   Create `src/utils/config_utils.py`.
        *   Move `create_config_template` and `default_settings` into this new file.
        *   Update any external references if they exist.

2.  **Improve Logging in `Settings.load_config_files`:**
    *   **Issue:** The `load_config_files` method uses `print()` statements for warnings (e.g., `print(f"Warning: Could not load base config file...")`).
    *   **Recommendation:** Use the `logging` module for all warnings and errors to ensure consistent log handling across the application.
    *   **Action:**
        *   Import `logging` at the top of `src/core/config.py`.
        *   Replace `print(f"Warning: ...")` with `logging.warning(f"...")`.

3.  **Review Redundant `config_dir` Check in `Settings.load_config_files`:**
    *   **Issue:** Inside `load_config_files`, there's a check:
        ```python
        config_dir = values.get('config_dir')
        if not config_dir:
            config_dir = Path(__file__).parent.parent / "config"
        ```
        The `config_dir` is already defined as a `Field` with a `default_factory` in the `Settings` class, meaning it should always have a value when `model_validator(mode='before')` is called. This check might be redundant.
    *   **Recommendation:** Verify if `config_dir` can ever be `None` or empty at this point. If Pydantic's `default_factory` guarantees a value, this check can be removed.
    *   **Action:**
        *   Remove the redundant `if not config_dir:` block.

---

## `src/core/environment_loader.py`

### General Observations
This module provides essential environment variable loading capabilities. However, it contains duplicated logic and a potentially unnecessary function.

### Specific Recommendations

1.  **Remove Duplicate `_deep_merge_dicts` Function:**
    *   **Issue:** The `_deep_merge_dicts` function in this file is identical to `_deep_merge` in `src/core/config.py`.
    *   **Recommendation:** Remove this duplicate function. The `_deep_merge` function from `src/core/config.py` can be imported and reused if needed, or a common utility module for such helpers should be created. Given `Settings.load_config_files` already uses `_deep_merge` from `config.py`, this one is likely unused.
    *   **Action:**
        *   Delete the `_deep_merge_dicts` function from `src/core/environment_loader.py`.

2.  **Evaluate Necessity of `load_config_with_env` Function:**
    *   **Issue:** The `load_config_with_env` function appears to duplicate the core logic of loading and merging configuration files, which is already handled by the `Settings.load_config_files` `model_validator` in `src/core/config.py`.
    *   **Recommendation:** If the `Settings` class is the primary and intended way to load the application's configuration, then `load_config_with_env` is likely redundant and can be removed. If it serves a specific, distinct purpose (e.g., for a separate CLI tool that doesn't use the `Settings` Pydantic model), then it should be clearly documented and potentially moved to a `utils` module.
    *   **Action:**
        *   If `load_config_with_env` is not used elsewhere, remove it.

---

## `src/data_sources/scrapers/wiki_scraper.py`

### General Observations
This is a complex module responsible for web scraping. It's generally well-structured with good error handling and caching. The main areas for improvement are consistency in metric updates and potentially more robust HTML parsing.

### Specific Recommendations

1.  **Consolidate Metric Updates:**
    *   **Issue:** The `_update_metrics` function is called in `fetch_champion_page`, but `parse_champion_stats_safe` and `parse_champion_abilities_safe` also directly increment `self.metrics.parsing_successes` and `self.metrics.parsing_failures`. This can lead to double-counting or inconsistent metric reporting.
    *   **Recommendation:** Ensure that metric updates are centralized. `_update_metrics` should be the single source for updating `parsing_successes` and `parsing_failures`. The `_safe` parsing methods should call `_update_metrics` with appropriate `success` and `error` parameters, or `_update_metrics` should be called only once at the end of the `fetch_champion_page` after all parsing attempts.
    *   **Action:**
        *   Modify `parse_champion_stats_safe` and `parse_champion_abilities_safe` to *not* directly increment `self.metrics.parsing_successes` or `self.metrics.parsing_failures`. Instead, they should return a status (e.g., `True`/`False` for success) and the error message, which `fetch_champion_page` then uses to call `_update_metrics` once.

2.  **Improve HTML Parsing Robustness (Long-term):**
    *   **Issue:** Many parsing functions (`_find_stats_section`, `_find_abilities_section`, `_extract_stat_value`, `_extract_single_ability`, etc.) rely heavily on text content, general class names, and regex. This makes the scraper brittle and highly susceptible to breaking if the LoL Wiki's HTML structure changes.
    *   **Recommendation:** While a complete overhaul might be out of scope for a quick fix, for future improvements, consider:
        *   **More specific CSS selectors:** If the wiki uses stable IDs or more unique class combinations, target those.
        *   **XPath:** XPath can be more powerful for navigating complex HTML trees.
        *   **Data attributes:** If the wiki uses `data-*` attributes for semantic information, these are often more stable than visual classes.
    *   **Action:**
        *   This is a long-term architectural recommendation. No immediate code change is required unless a parsing issue arises.

3.  **Review `__copy__` Usage in `_find_abilities_section`:**
    *   **Issue:** The `_find_abilities_section` method uses `element.__copy__()` when creating the `wrapper` div. While this creates a copy, it might be unnecessary if the intent is simply to move or re-parent the elements, or if `BeautifulSoup`'s default behavior for appending elements is sufficient.
    *   **Recommendation:** Verify if `element.__copy__()` is strictly necessary. If the original `soup` object is not modified in a way that would be problematic by directly appending `element` (which would move it), then `__copy__` might add overhead. If the goal is to create a new `BeautifulSoup` object from a subset of the original, then `BeautifulSoup(str(element))` might be clearer.
    *   **Action:**
        *   Review the specific use case. If direct appending or `BeautifulSoup(str(element))` achieves the same result without unintended side effects, simplify the code.

---

## `src/mcp_server/mcp_handler.py`

### General Observations
This module handles the MCP protocol. The main area for improvement is the separation and management of "basic tools" versus "LoL data tools."

### Specific Recommendations

1.  **Unify Tool Management under `ToolRegistry`:**
    *   **Issue:** The `MCPHandler` currently manages two distinct sets of tools: `self.tool_registry` for LoL-specific tools and `self.basic_tools` (a dictionary) for basic functionalities like `ping` and `server_info`. This leads to duplicated logic in `initialize`, `_handle_list_tools`, and `_handle_call_tool`.
    *   **Recommendation:** Consolidate all tools under the `ToolRegistry` system. This would make tool management more consistent, scalable, and easier to extend. Basic tools can be defined as regular `MCPTool` implementations and registered with the `ToolRegistry`.
    *   **Action:**
        *   Define `PingTool` and `ServerInfoTool` classes that inherit from `MCPTool` in `src/mcp_server/tools.py`.
        *   Move the `_handle_ping_tool` and `_handle_server_info_tool` logic into the `execute` methods of these new tool classes.
        *   Register these new tools with `ToolRegistry` in `ToolRegistry._register_default_tools`.
        *   Remove `self.basic_tools` dictionary and all related logic from `MCPHandler`.
        *   Simplify `initialize`, `_handle_list_tools`, and `_handle_call_tool` to only interact with `self.tool_registry`.

---

## `src/mcp_server/server.py`

### General Observations
This module sets up the FastAPI server. The signal handling could be improved for more graceful shutdown.

### Specific Recommendations

1.  **Improve Graceful Shutdown in `_setup_signal_handlers`:**
    *   **Issue:** The `_setup_signal_handlers` uses `sys.exit(0)` for `SIGINT` and `SIGTERM`. While this exits the process, it's not the most graceful way to shut down an asynchronous application, as it bypasses FastAPI/Uvicorn's shutdown hooks.
    *   **Recommendation:** For FastAPI/Uvicorn applications, it's generally better to let Uvicorn handle signals or to trigger an asynchronous shutdown process. Uvicorn's `lifespan` context manager (already in use) is designed for this. If custom shutdown logic is needed beyond `lifespan`, consider using `asyncio.create_task` to run a shutdown coroutine that cleans up resources.
    *   **Action:**
        *   Remove the custom `_setup_signal_handlers` method. Uvicorn typically handles `SIGINT` and `SIGTERM` gracefully by default, triggering the `lifespan`'s `yield` block to complete.

---

## `src/mcp_server/stdio_server.py`

### General Observations
This module provides a stdio-based MCP server. The main issues are related to Python's module import system and potential import redundancy.

### Specific Recommendations

1.  **Refactor Module Import Paths:**
    *   **Issue:** The module uses `sys.path.insert(0, str(project_root))` and `sys.path.insert(0, str(src_dir))` to manage imports, along with a `try-except` block for `MCPHandler` import (`from mcp_server.mcp_handler import MCPHandler` vs `from src.mcp_server.mcp_handler import MCPHandler`). This approach is brittle, non-portable, and can lead to module resolution issues.
    *   **Recommendation:** Adopt standard Python relative or absolute imports based on the package structure. The `src` directory should be treated as a Python package. If `stdio_server.py` is meant to be run directly, ensure the project's root is correctly added to `PYTHONPATH` externally (e.g., via a `run.sh` script or `pyproject.toml` configuration) rather than modifying `sys.path` within the code.
    *   **Action:**
        *   Remove all `sys.path.insert` calls.
        *   Simplify the `MCPHandler` import to a single, consistent absolute import: `from src.mcp_server.mcp_handler import MCPHandler`.
        *   Ensure the environment where this script is run has the project root (or `src` directory) correctly added to `PYTHONPATH`.

---

## `src/mcp_server/tools.py`

### General Observations
This module defines the MCP tools and their registry. The lazy initialization of `ChampionService` is a valid pattern but could be optimized.

### Specific Recommendations

1.  **Optimize `ChampionService` Initialization in Tools:**
    *   **Issue:** `GetChampionDataTool` and `GetAbilityDetailsTool` both use `_get_champion_service` to lazily initialize `ChampionService`. This means a new `ChampionService` instance is created every time `_get_champion_service` is called within an `execute` method, which could be inefficient if `ChampionService` holds state or is expensive to instantiate.
    *   **Recommendation:** Pass an already initialized `ChampionService` instance to the `MCPTool` constructors (e.g., when `ToolRegistry` registers them). This promotes dependency injection and ensures `ChampionService` is a singleton or managed appropriately.
    *   **Action:**
        *   Modify `MCPTool` (or a new base class for service-dependent tools) to accept a `ChampionService` instance in its `__init__`.
        *   In `ToolRegistry._register_default_tools`, instantiate `ChampionService` once and pass it to `GetChampionDataTool` and `GetAbilityDetailsTool` during their creation.
        *   Remove the `_get_champion_service` methods from `GetChampionDataTool` and `GetAbilityDetailsTool`.

---

## `src/services/champion_service.py`

### General Observations
This is a core service module that integrates with the `WikiScraper` and provides champion data. It's generally well-designed with Pydantic models and fallback mechanisms. The main areas for improvement are minor redundancies and consistency in data transformation/scaling.

### Specific Recommendations

1.  **Remove Redundant `include` Default Check:**
    *   **Issue:** In `get_champion_data`, there's a check `if include is None: include = ["stats", "abilities"]`. This is redundant because the `GetChampionDataInput` Pydantic model (which `include` is validated against) already defines `include` with a `default=["stats", "abilities"]`.
    *   **Recommendation:** Remove this redundant check. The `validated_input` will always have a default `include` list if not provided by the caller.
    *   **Action:**
        *   Delete the line: `if include is None: include = ["stats", "abilities"]`.

2.  **Consolidate Stat Scaling Logic:**
    *   **Issue:** Stat scaling logic is present in two places:
        1.  `_transform_wiki_stats`: Applies scaling if `level` is provided.
        2.  `get_champion_data`: Applies scaling *after* `champion_data.stats.model_dump()` if `level` is provided.
        This could lead to double scaling or confusion if not carefully managed.
    *   **Recommendation:** Consolidate stat scaling to a single, clear point. It's generally better to apply scaling *after* the raw data is transformed into the `ChampionStats` model, or have `_transform_wiki_stats` *always* return base stats, and `get_champion_data` *then* applies scaling based on the requested `level`.
    *   **Action:**
        *   Modify `_transform_wiki_stats` to *always* return base stats (i.e., remove the `if level and growth_val is not None:` block and the `_scale_stat` call within it).
        *   Ensure the scaling logic in `get_champion_data` is the *only* place where stats are scaled based on the `level` parameter. This makes the flow clearer: raw wiki data -> base stats model -> scaled stats for response.

3.  **Review `stats_note` and `abilities_note` in Response:**
    *   **Issue:** The `get_champion_data` method adds `stats_note` and `abilities_note` to the response if data is not available from the source. While useful for debugging, these might not be desired in a production API response.
    *   **Recommendation:** Consider making these notes optional, perhaps controlled by a debug flag in the settings, or removing them for production environments. For an AI consumer, a `None` value for `stats` or `abilities` might be sufficient to indicate unavailability.
    *   **Action:**
        *   If these notes are not intended for production, wrap their inclusion in an `if self.debug_mode:` check (assuming a `debug_mode` attribute is added to `ChampionService` from settings). Otherwise, remove them.

4.  **Refine `_get_champion_from_wiki` Error Handling and Data Structure:**
    *   **Issue:** The "Fix" comments in `_get_champion_from_wiki` indicate that `wiki_stats` and `wiki_abilities` might return different structures on success vs. failure (e.g., `{'error': ..., 'stats': {}}` vs. just `{}`). This makes the subsequent `if 'error' not in wiki_stats and wiki_stats:` checks a bit convoluted.
    *   **Recommendation:** Ensure `WikiScraper.parse_champion_stats_safe` and `parse_champion_abilities_safe` consistently return a dictionary with a clear `success` boolean and a `data` key (or `error` key) to simplify handling in `_get_champion_from_wiki`.
    *   **Action:**
        *   Modify `WikiScraper.parse_champion_stats_safe` and `parse_champion_abilities_safe` to return a consistent structure, e.g., `{'success': True, 'data': {...}}` or `{'success': False, 'error': '...'}`.
        *   Update `_get_champion_from_wiki` to reflect this consistent structure, simplifying the checks for `stats` and `abilities` availability.

5.  **Placeholder Data for `builds` and `history`:**
    *   **Issue:** The `builds` and `history` sections in `get_champion_data` currently return mock data with a "note" indicating they are not yet implemented.
    *   **Recommendation:** This is fine for placeholders. Ensure that when these features are implemented, the mock data and notes are replaced with actual data retrieval logic.
    *   **Action:**
        *   No immediate action, but keep in mind for future feature development.

---