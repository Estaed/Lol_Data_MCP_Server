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

---

## `src/data_sources/scrapers/abilities_scraper.py`

### Recommendation 9: Simplify Dual-Form Detection

**Why:**
The `_detect_dual_form_http_fast` and `_detect_dual_form_with_selenium` methods are complex and have overlapping logic. They can be simplified and consolidated. The HTTP-based detection is prone to errors and the Selenium-based detection can be slow.

**How:**
Rely primarily on the more robust Selenium-based detection, but simplify the selectors. The current implementation has a long list of selectors, many of which are redundant. A single, well-chosen selector is often sufficient.

**Recommended Code:**
```python
    async def _detect_dual_form(self, champion_name: str) -> bool:
        """Check if a champion has dual forms using a simplified Selenium approach."""
        driver = None
        try:
            driver = self._create_selenium_driver()
            url = self._build_champion_url(champion_name)
            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # A single, reliable selector for dual-form champions
            dual_form_element = driver.find_elements(By.CSS_SELECTOR, ".tabbernav")
            if dual_form_element:
                self.logger.info(f"Dual form detected for {champion_name}")
                return True
            
            self.logger.info(f"No dual form detected for {champion_name}")
            return False
            
        except Exception as e:
            self.logger.warning(f"Failed to detect dual form for {champion_name}: {e}")
            return False
        finally:
            if driver:
                driver.quit()
```

### Recommendation 10: Refactor Ability Extraction

**Why:**
The ability extraction logic is spread across many methods, making it difficult to follow. The code for single-form, dual-form, and special cases (Aphelios) can be better organized.

**How:**
Create a main extraction method that delegates to specialized methods based on the champion's type. This will make the code more modular and easier to maintain.

**Recommended Code:**
```python
    async def scrape_champion_abilities(self, champion_name: str) -> Dict[str, Any]:
        """Scrape all champion abilities from the champion's wiki page."""
        self.logger.info(f"Scraping abilities for {champion_name}")
        
        if champion_name.lower() == 'aphelios':
            return await self._scrape_aphelios_weapon_system(champion_name)
        
        has_dual_form = await self._detect_dual_form(champion_name)
        
        if has_dual_form:
            return await self._scrape_dual_form_abilities(champion_name)
        else:
            return await self._scrape_single_form_abilities(champion_name)
```

### Recommendation 11: Consolidate Text Cleaning

**Why:**
The `_apply_text_cleaning_rules` and `_clean_description_text` methods have similar purposes. They can be combined into a single, comprehensive cleaning function.

**How:**
Merge the logic of both methods into one, and apply it consistently throughout the scraper.

**Recommended Code:**
```python
    def _clean_text(self, text: str) -> str:
        """Apply all text cleaning rules."""
        if not text:
            return ""
        
        # Remove UI elements
        text = re.sub(r'^Edit\s+', '', text, flags=re.IGNORECASE)
        
        # Standardize whitespace and special characters
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('\u2013', '-').replace('\u2014', '-')
        
        # ... other cleaning rules ...
        
        return text.strip()
```

---

## `src/services/abilities_service.py`

### Recommendation 12: Simplify Ability Slot Normalization

**Why:**
The `_normalize_ability_slot` method uses a dictionary for mapping, which is good, but it can be made more concise.

**How:**
Use a more compact dictionary initialization.

**Recommended Code:**
```python
    def _normalize_ability_slot(self, ability_slot: Optional[str]) -> Optional[str]:
        """Normalize ability slot name."""
        if not ability_slot:
            return None
        
        slot = ability_slot.strip().upper()
        
        slot_mapping = {
            'P': 'Passive', 'PASSIVE': 'Passive',
            'Q': 'Q',
            'W': 'W',
            'E': 'E',
            'R': 'R', 'ULT': 'R', 'ULTIMATE': 'R'
        }
        
        return slot_mapping.get(slot, slot)
```

### Recommendation 13: Improve Error Handling

**Why:**
The `get_champion_abilities` method has complex error handling logic. It catches `WikiScraperError` and `ValueError` and re-raises them as `ChampionNotFoundError`. This can obscure the original error.

**How:**
Simplify the error handling by letting `WikiScraperError` propagate. This will provide more specific error messages to the caller.

**Recommended Code:**
```python
    async def get_champion_abilities(self, champion: str, ability_slot: Optional[str] = None) -> Dict[str, Any]:
        # ...
        try:
            # ...
        except WikiScraperError as e:
            self.logger.error(f"Failed to get champion abilities for {champion_name}: {e}")
            raise  # Re-raise the original exception
```

---

## Configuration Files

### Recommendation 14: Consolidate Configuration

**Why:**
There is some redundancy between `server_config.yaml`, `development_config.yaml`, and `production_config.yaml`. This can make it difficult to manage the configuration and can lead to inconsistencies.

**How:**
Define a base configuration in `server_config.yaml` and only include the environment-specific overrides in `development_config.yaml` and `production_config.yaml`. This will make the configuration more modular and easier to maintain.

**Example:**

`server_config.yaml` (Base Configuration):
```yaml
server:
  host: "0.0.0.0"
  port: 8000

database:
  pool_size: 10
  max_overflow: 20
```

`development_config.yaml` (Overrides):
```yaml
server:
  debug: true
  workers: 1

database:
  url: "postgresql://user:pass@localhost/dev_db"
```

`production_config.yaml` (Overrides):
```yaml
server:
  debug: false
  workers: 4

database:
  url: "${DATABASE_URL}"
```

### Recommendation 15: Enhance Tool Descriptions in `mcp_tools.yaml`

**Why:**
The `mcp_tools.yaml` file provides a good overview of the available tools, but the descriptions could be more detailed. This would make it easier for developers to understand how to use the tools.

**How:**
Add more detailed descriptions and examples for each tool in the `mcp_tools.yaml` file.

**Example:**
```yaml
tools:
  get_champion_data:
    enabled: true
    description: "Retrieves comprehensive data for a specific champion, including base stats, abilities, and recommended builds. This tool can be used to get a complete overview of a champion's capabilities."
    category: "champion_data"
    schema:
      properties:
        champion:
          description: "The name of the champion to retrieve data for."
          examples: ["Taric", "Jinx", "Yasuo"]
```

---

## `src/core/config.py`

### Recommendation 16: Simplify Configuration Loading

**Why:**
The `load_config_files` method in `Settings` is responsible for loading and merging multiple configuration files. This logic can be simplified by using a more standard approach to configuration management.

**How:**
Instead of manually loading and merging the files, you can leverage `pydantic-settings` ability to load from multiple sources. You can define a base settings class and then create environment-specific settings classes that inherit from it.

**Recommended Code:**
```python
class BaseAppSettings(BaseSettings):
    # Common settings

class DevAppSettings(BaseAppSettings):
    # Development-specific settings
    class Config:
        env_file = 'config/development.env'

class ProdAppSettings(BaseAppSettings):
    # Production-specific settings
    class Config:
        env_file = 'config/production.env'

def get_app_settings() -> BaseAppSettings:
    env = os.getenv("APP_ENV", "development")
    if env == "production":
        return ProdAppSettings()
    return DevAppSettings()
```

---

## `src/mcp_server/mcp_handler.py`

### Recommendation 17: Use a More Specific Exception

**Why:**
The `handle_message` method catches a generic `Exception`. This can make it difficult to debug issues, as it can hide the original exception.

**How:**
Catch more specific exceptions, such as `KeyError` or `ValueError`, and provide more informative error messages.

**Recommended Code:**
```python
    async def handle_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            method = message["method"]
            # ...
        except KeyError:
            return self._create_error_response(message.get("id"), -32600, "Invalid Request: Missing 'method'")
        except Exception as e:
            # ...
```

---

## `src/models/input_models.py`

### Recommendation 18: Add More Granular Validation

**Why:**
The `GetChampionDataInput` model validates that the `include` field contains valid options. However, it could also validate the `champion` field to ensure that it is not an empty string.

**How:**
Add a validator for the `champion` field to ensure that it is not empty.

**Recommended Code:**
```python
class GetChampionDataInput(BaseModel):
    # ...

    @field_validator("champion")
    @classmethod
    def validate_champion_name(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Champion name cannot be empty")
        return v
```

---

## `src/services/abilities_service.py`

### Recommendation 19: Simplify Error Handling

**Why:**
The `get_champion_abilities` method has complex error handling logic. It catches `WikiScraperError` and `ValueError` and re-raises them as `ChampionNotFoundError`. This can obscure the original error.

**How:**
Simplify the error handling by letting `WikiScraperError` propagate. This will provide more specific error messages to the caller.

**Recommended Code:**
```python
    async def get_champion_abilities(self, champion: str, ability_slot: Optional[str] = None) -> Dict[str, Any]:
        # ...
        try:
            # ...
        except WikiScraperError as e:
            self.logger.error(f"Failed to get champion abilities for {champion_name}: {e}")
            raise  # Re-raise the original exception
```

---

## `tests`

### Recommendation 20: Increase Test Coverage

**Why:**
The existing tests provide a good starting point, but they could be more comprehensive. Increasing the test coverage will help to ensure the quality and robustness of the application.

**How:**
Add more tests to cover the edge cases and error conditions. For example, you could add tests for the following:

*   **`test_abilities_service.py`:**
    *   Test with champions that have different numbers of abilities.
    *   Test with champions that have special characters in their names.
*   **`test_stats_service.py`:**
    *   Test with different levels, including the minimum and maximum levels.
    *   Test with champions that have different resource types.

**Example:**
```python
# In test_abilities_service.py
@pytest.mark.asyncio
asyn def test_get_champion_abilities_with_special_characters(self, abilities_service_with_wiki, mock_abilities_data):
    # ...

# In test_stats_service.py
@pytest.mark.asyncio
asyn def test_get_champion_stats_with_max_level(self, stats_service, mock_stats_scraper):
    # ...
```
