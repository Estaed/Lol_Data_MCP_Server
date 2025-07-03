# Codebase Improvement Recommendations for Lol_Data_MCP_Server

This document provides a detailed analysis of the Python files within the `src` directory, highlighting areas for improvement in terms of redundancy, clarity, efficiency, maintainability, error handling, modularity, and adherence to best practices. The recommendations are structured to be directly actionable.

---

## `src/data_sources/scrapers/wiki_scraper.py`

### General Observations
This is a complex module responsible for web scraping. It's generally well-structured with good error handling and caching. The main areas for improvement are more robust HTML parsing.

### Specific Recommendations

1.  **Improve HTML Parsing Robustness (Long-term):**
    *   **Issue:** Many parsing functions (`_find_stats_section`, `_find_abilities_section`, `_extract_stat_value`, `_extract_single_ability`, etc.) rely heavily on text content, general class names, and regex. This makes the scraper brittle and highly susceptible to breaking if the LoL Wiki's HTML structure changes.
    *   **Recommendation:** While a complete overhaul might be out of scope for a quick fix, for future improvements, consider:
        *   **More specific CSS selectors:** If the wiki uses stable IDs or more unique class combinations, target those.
        *   **XPath:** XPath can be more powerful for navigating complex HTML trees.
        *   **Data attributes:** If the wiki uses `data-*` attributes for semantic information, these are often more stable than visual classes.
    *   **Action:**
        *   This is a long-term architectural recommendation. No immediate code change is required unless a parsing issue arises.

2.  **Review `__copy__` Usage in `_find_abilities_section`:**
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

## `src/services/champion_service.py`

### General Observations
This is a core service module that integrates with the `WikiScraper` and provides champion data. It's generally well-designed with Pydantic models and fallback mechanisms. The main areas for improvement are consistency in data transformation/scaling.

### Specific Recommendations

1.  **Consolidate Stat Scaling Logic:**
    *   **Issue:** Stat scaling logic is present in two places:
        1.  `_transform_wiki_stats`: Applies scaling if `level` is provided.
        2.  `get_champion_data`: Applies scaling *after* `champion_data.stats.model_dump()` if `level` is provided.
        This could lead to double scaling or confusion if not carefully managed.
    *   **Recommendation:** Consolidate stat scaling to a single, clear point. It's generally better to apply scaling *after* the raw data is transformed into the `ChampionStats` model, or have `_transform_wiki_stats` *always* return base stats, and `get_champion_data` *then* applies scaling based on the requested `level`.
    *   **Action:**
        *   Modify `_transform_wiki_stats` to *always* return base stats (i.e., remove the `if level and growth_val is not None:` block and the `_scale_stat` call within it).
        *   Ensure the scaling logic in `get_champion_data` is the *only* place where stats are scaled based on the `level` parameter. This makes the flow clearer: raw wiki data -> base stats model -> scaled stats for response.

2.  **Review `stats_note` and `abilities_note` in Response:**
    *   **Issue:** The `get_champion_data` method adds `stats_note` and `abilities_note` to the response if data is not available from the source. While useful for debugging, these might not be desired in a production API response.
    *   **Recommendation:** Consider making these notes optional, perhaps controlled by a debug flag in the settings, or removing them for production environments. For an AI consumer, a `None` value for `stats` or `abilities` might be sufficient to indicate unavailability.
    *   **Action:**
        *   If these notes are not intended for production, wrap their inclusion in an `if self.debug_mode:` check (assuming a `debug_mode` attribute is added to `ChampionService` from settings). Otherwise, remove them.

3.  **Refine `_get_champion_from_wiki` Error Handling and Data Structure:**
    *   **Issue:** The "Fix" comments in `_get_champion_from_wiki` indicate that `wiki_stats` and `wiki_abilities` might return different structures on success vs. failure (e.g., `{'error': ..., 'stats': {}}` vs. just `{}`). This makes the subsequent `if 'error' not in wiki_stats and wiki_stats:` checks a bit convoluted.
    *   **Recommendation:** Ensure `WikiScraper.parse_champion_stats_safe` and `parse_champion_abilities_safe` consistently return a dictionary with a clear `success` boolean and a `data` key (or `error` key) to simplify handling in `_get_champion_from_wiki`.
    *   **Action:**
        *   Modify `WikiScraper.parse_champion_stats_safe` and `parse_champion_abilities_safe` to return a consistent structure, e.g., `{'success': True, 'data': {...}}` or `{'success': False, 'error': '...'}`.
        *   Update `_get_champion_from_wiki` to reflect this consistent structure, simplifying the checks for `stats` and `abilities` availability.
