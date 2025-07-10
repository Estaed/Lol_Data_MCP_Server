# Code Review Recommendations

This document provides recommendations for improving the codebase of the LoL Data MCP Server. The focus is on enhancing readability, robustness, and maintainability.

---

## `src/core/config.py`

### Recommendation 1: Remove Redundant `config_dir` Check

**Why:**
The `load_config_files` method checks if `config_dir` exists in the `values` dictionary. However, the `config_dir` field in the `Settings` model has a `default_factory`, which ensures that the value is always present. The check is therefore redundant and can be safely removed.

**Original Code:**
```python
    @model_validator(mode='before')
    @classmethod
    def load_config_files(cls, values):
        """Load configuration from YAML files with environment-specific overrides."""
        config_dir = values.get('config_dir')
        # ...
```

**Recommended Code:**
```python
    @model_validator(mode='before')
    @classmethod
    def load_config_files(cls, values):
        """Load configuration from YAML files with environment-specific overrides."""
        config_dir = values.get('config_dir', Path(__file__).parent.parent / "config")
        # ...
```

### Recommendation 2: Use `logging` Instead of `print`

**Why:**
The `load_config_files` method uses `print()` to log warnings when configuration files cannot be loaded. For consistency with the rest of the application and to enable better log management (e.g., routing logs to different outputs, setting log levels), it is better to use the `logging` module.

**Original Code:**
```python
                # Fallback to defaults if config file can't be loaded
                print(f"Warning: Could not load base config file {base_config_path}: {e}")
```

**Recommended Code:**
```python
                # Fallback to defaults if config file can't be loaded
                logging.warning(f"Could not load base config file {base_config_path}: {e}")
```

---

## `src/core/environment_loader.py`

### Recommendation 3: Use `logging` Instead of `print`

**Why:**
Similar to the previous recommendation, the `validate_required_env_vars` function uses `print()` for warnings. This should be replaced with `logging.warning()` for consistent logging behavior.

**Original Code:**
```python
                print(f"Warning: Could not validate environment variables in {file_path}: {e}")
```

**Recommended Code:**
```python
                logging.warning(f"Could not validate environment variables in {file_path}: {e}")
```

---

## `src/data_sources/scrapers/base_scraper.py`

### Recommendation 4: Simplify `_update_metrics` Method

**Why:**
The `_update_metrics` method currently handles both request metrics and parsing metrics. This dual responsibility can be confusing. It would be clearer to separate these concerns.

**How:**
Refactor `_update_metrics` to only handle request-related metrics. The parsing metrics can be updated directly in the methods that perform the parsing.

**Recommended Code:**
```python
    def _update_request_metrics(self, start_time: float, cache_hit: bool = False, error: Optional[str] = None) -> None:
        """Update scraping performance metrics for requests."""
        if cache_hit:
            self.metrics.cache_hits += 1
        else:
            self.metrics.cache_misses += 1
            request_time = time.monotonic() - start_time
            self.metrics.total_request_time += request_time
            self.metrics.total_requests += 1
            if self.metrics.total_requests > 0:
                self.metrics.avg_request_time = self.metrics.total_request_time / self.metrics.total_requests

        if error:
            self.metrics.errors.append(error)

    def _update_parsing_metrics(self, success: bool, error: Optional[str] = None) -> None:
        """Update scraping performance metrics for parsing."""
        if success:
            self.metrics.parsing_successes += 1
        else:
            self.metrics.parsing_failures += 1
            if error:
                self.metrics.errors.append(error)
```

---

## `src/data_sources/scrapers/stats_scraper.py`

### Recommendation 5: Improve Robustness with Explicit Waits

**Why:**
The `scrape_level_specific_stats` method uses `time.sleep(1.0)` to wait for the page to update. This is brittle. Using `WebDriverWait` makes the scraper more reliable.

**How:**
Wait for a specific condition to be met, such as the text of a stat element changing.

**Recommended Code:**
```python
            # ...
            level_dropdown.select_by_value(str(level))
            
            # Wait for a stat to update, indicating the JS has run
            try:
                wait.until(
                    EC.text_to_be_present_in_element(
                        (By.CSS_SELECTOR, LEVEL_SELECTORS['hp']), "some_expected_text"
                    )
                )
            except TimeoutException:
                self.logger.warning("Timed out waiting for stats to update.")

            # ...
```

### Recommendation 6: Simplify Resource Type Detection

**Why:**
The current logic for determining the resource type is complex. It can be simplified into a more direct and readable method.

**How:**
Create a single method that inspects the page and returns the resource type.

**Recommended Code:**
```python
    def _get_resource_type(self, soup: BeautifulSoup) -> str:
        """Determines the champion's resource type from the page soup."""
        if soup.select_one('#ResourceRegen_'):
            return "mana"
        if soup.select_one('#Energy_'):
            return "energy"
        return "secondary_bar"
```

### Recommendation 7: Consolidate Stat Extraction Logic

**Why:**
The logic for extracting stats is duplicated between `scrape_level_specific_stats` and `scrape_default_stat_ranges`. This should be consolidated into a single helper function.

**How:**
Create a new private method, `_extract_stats_from_soup`, that takes a `BeautifulSoup` object and extracts the stats.

**Recommended Code:**
```python
    def _extract_stats_from_soup(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extracts stats from a BeautifulSoup object."""
        stats = {}
        # ... logic to extract all stats from the soup ...
        return stats

    async def scrape_level_specific_stats(self, champion_name: str, level: int) -> Dict[str, Any]:
        # ... selenium logic ...
        soup = BeautifulSoup(driver.page_source, "lxml")
        stats = self._extract_stats_from_soup(soup)
        # ...
        
    async def scrape_default_stat_ranges(self, champion_name: str) -> Dict[str, Any]:
        soup = await self.fetch_champion_page(champion_name)
        stats = self._extract_stats_from_soup(soup)
        # ...
```

---

## `src/mcp_server/tools.py`

### Recommendation 8: Use Dependency Injection for Services

**Why:**
The `_register_default_tools` method in `ToolRegistry` directly imports and instantiates `StatsService`. This creates a tight coupling. Using dependency injection would make the code more modular and easier to test.

**How:**
Pass the `StatsService` instance to the tools that need it in their constructor.

**Recommended Code:**
```python
# In GetChampionStatsTool
class GetChampionStatsTool(MCPTool):
    def __init__(self, stats_service: StatsService):
        super().__init__(...)
        self._stats_service = stats_service

# In ToolRegistry
class ToolRegistry:
    def __init__(self, stats_service: StatsService):
        self.tools: Dict[str, MCPTool] = {}
        self._stats_service = stats_service
        self._register_default_tools()

    def _register_default_tools(self):
        self.register_tool(GetChampionStatsTool(self._stats_service))
        # ...
```
