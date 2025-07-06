# Wiki Page CSS Selectors

Please provide the CSS selectors for the following data points from the LoL Wiki.
This file will be used to configure the `WikiScraper` to ensure it can accurately extract data for all required tasks.

---

## Task 2.1.8: Per-Level Stat Scraping

**Objective:** Scrape the full table of champion stats for all 18 levels to ensure 100% accuracy. To do this, we need to interact with the level dropdown menu.

- **Level Dropdown Selector:**
  - *Description*: The selector for the `<select>` element of the level dropdown menu.
  - *Selector*: #lvl_

- **HP Value Selector:**
  - *Description*: The specific selector for the element containing the **HP value**.
  - *Selector*: #Health__lvl

- **Mana (MP) Value Selector:**
  - *Description*: The selector for the element containing the **Mana value**.
  - *Selector*: #ResourceBar__lvl

- **HP Regen (HP5) Value Selector:**
  - *Description*: The selector for the element containing the **HP Regen value**.
  - *Selector*: #HealthRegen__lvl

- **Mana Regen (MP5) Value Selector:**
  - *Description*: The selector for the element containing the **Mana Regen value**.
  - *Selector*: #ResourceRegen__lvl

- **Armor (AR) Value Selector:**
  - *Description*: The selector for the element containing the **Armor value**.
  - *Selector*: #Armor__lvl

- **Attack Damage (AD) Value Selector:**
  - *Description*: The selector for the element containing the **Attack Damage value**.
  - *Selector*: #AttackDamage__lvl

- **Magic Resist (MR) Value Selector:**
  - *Description*: The selector for the element containing the **Magic Resist value**.
  - *Selector*: #MagicResist__lvl

- **Crit. DMG Value Selector:**
  - *Description*: The selector for the element containing the **Critical Damage value**.
  - *Selector*: #mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(2) > div:nth-child(8) > div.infobox-data-value.statsbox

- **Movement Speed (MS) Value Selector:**
  - *Description*: The selector for the element containing the **Movement Speed value**.
  - *Selector*: #MovementSpeed_

- **Attack Range Value Selector:**
  - *Description*: The selector for the element containing the **Attack Range value**.
  - *Selector*: #AttackRange_

- **Base Attack Speed (Base AS) Value Selector:**
  - *Description*: The selector for the element containing the **Base Attack Speed value**.
  - *Selector*: #mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(1) > div.infobox-data-value.statsbox

- **Windup% Value Selector:**
  - *Description*: The selector for the element containing the **Windup Percent value**.
  - *Selector*: #mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(2) > div.infobox-data-value.statsbox

- **AS Ratio Value Selector:**
  - *Description*: The selector for the element containing the **Attack Speed Ratio value**.
  - *Selector*: #mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(4) > div:nth-child(3) > div.infobox-data-value.statsbox

- **Bonus AS Value Selector:**
  - *Description*: The selector for the element containing the **Bonus Attack Speed value**.
  - *Selector*: #AttackSpeedBonus__lvl

---

## Task 2.1.9: Enhanced Champion Basic Stats

**Objective:** Extract additional unit information for simulations and advanced analysis.

- **Gameplay Radius Selector:**
  - *Description*: The selector for the element containing the **Gameplay Radius value**.
  - *Selector*: #mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(6) > div:nth-child(1) > div.infobox-data-value.statsbox
- **Selection Radius Selector:**
  - *Description*: The selector for the element containing the **Selection Radius value**.
  - *Selector*: #mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(6) > div:nth-child(2) > div.infobox-data-value.statsbox
- **Pathing Radius Selector:**
  - *Description*: The selector for the element containing the **Pathing Radius value**.
  - *Selector*: #mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(6) > div:nth-child(3) > div.infobox-data-value.statsbox
- **Selection Height Selector:**
  - *Description*: The selector for the element containing the **Selection Height value**.
  - *Selector*: #mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(6) > div:nth-child(4) > div.infobox-data-value.statsbox
- **Acquisition Radius Selector:**
  - *Description*: The selector for the element containing the **Acquisition Radius value**.
  - *Selector*: #mw-content-text > div.mw-parser-output > div.champion-info > div.infobox.lvlselect.type-champion-stats.lvlselect-initialized > div:nth-child(6) > div:nth-child(5) > div.infobox-data-value.statsbox

---

## Task 2.1.10: Comprehensive Ability Detail System

**Objective:** Scrape detailed gameplay mechanics for each ability. The scraper will find each ability's main container first, then extract the details from within it.

- **Passive Ability Container Selector:**
  - *Description*: The selector for the main `div` that contains the **entire Passive ability block**.
  - *Selector*: #mw-content-text > div.mw-parser-output > div.skill.skill_innate
- **Q Ability Container Selector:**
  - *Description*: The selector for the main `div` that contains the **entire Q ability block**.
  - *Selector*: #mw-content-text > div.mw-parser-output > div.skill.skill_q
- **W Ability Container Selector:**
  - *Description*: The selector for the main `div` that contains the **entire W ability block**.
  - *Selector*: #mw-content-text > div.mw-parser-output > div.skill.skill_w
- **E Ability Container Selector:**
  - *Description*: The selector for the main `div` that contains the **entire E ability block**.
  - *Selector*: #mw-content-text > div.mw-parser-output > div.skill.skill_e
- **R Ability Container Selector:**
  - *Description*: The selector for the main `div` that contains the **entire R ability block**.
  - *Selector*: #mw-content-text > div.mw-parser-output > div.skill.skill_r

- **NOTE:** The long selectors above are valid, but it is **highly recommended** to simplify them to just the class name (e.g., `.skill_innate`, `.skill_q`) to make the scraper more resilient to website layout changes.

- **Ability Description Selector (within container):**
  - *Description*: The selector for the description `div`, relative to its container (e.g., `.ability-info-description`). The scraper will use this to find the description *inside* each of the ability containers listed above.
  - *Selector*: .ability-info-description
- **Ability Stats Container Selector (within container):**
  - *Description*: The selector for the list `div` that contains all the detailed stats (Cost, Cooldown, Cast Time, etc.). The scraper will find this *inside* each ability container and extract all the stats from it.
  - *Selector*: .ability-info-stats__list

---

## Task 2.1.11: Enhanced get_ability_details Tool

**Objective:** Extract the rich content from the "Details" tab for each ability by first clicking the tab with Selenium and then scraping the revealed content.

- **"Details" Tab Button Selector (within container):**
  - *Description*: The selector for the "Details" tab `<li>` or `<a>` element, relative to the ability's main container. The scraper will click this to reveal the details.
  - *Selector*: ul.tabbernav > li:nth-child(2)

- **"Details" Content Container Selector (within container):**
  - *Description*: The selector for the `div` that contains all the content of the "Details" tab. This becomes visible after the click. An example `div` might have `data-title="Details"`.
  - *Selector*: div.tabbertab[data-title="Details"]

- **Targeting Input Value Selector (within details container):**
  - *Description*: The selector for the value associated with "Targeting input" (e.g., the element containing "Passive").
  - *Selector*: .infobox-data-value

- **Damage Classification Type Value Selector (within details container):**
  - *Description*: The selector for the value under "Damage classification" for "Type" (e.g., the element containing "Proc damage").
  - *Selector*: .infobox-cell-2 .infobox-data-value

- **Damage Classification Sub-type(s) Value Selector (within details container):**
  - *Description*: The selector for the value under "Damage classification" for "Sub-type(s)" (e.g., the element containing "Magic").
  - *Selector*: .infobox-cell-3 .infobox-data-value

- **Full Description List Selector (within details container):**
  - *Description*: The selector for the `<ul>` on the left that contains the bullet points of the detailed description. The scraper will combine all list items into a full description.
  - *Selector*: .infobox-section-collapsible + .infobox-section-consist > div

---

## Task 2.1.12: Patch History Analysis Tool

**Objective:** Scrape historical patch note data for champions. The scraper will identify each patch version and then find the list of changes that immediately follows it.

- **Patch History Page Container:**
  - *Description*: The main container for the entire patch history section for a champion.
  - *Selector*: #Patch_history
- **Patch Version Selector (within container):**
  - *Description*: The selector for the element containing the patch version title (e.g., the `<dt>` element for "V14.21"). The scraper will loop through all of these.
  - *Selector*: dt
- **List of Changes Selector (relative to version):**
  - *Description*: The selector for the `<ul>` that contains the list of changes. The scraper will look for this *immediately after* finding a patch version element. In CSS, this is the "adjacent sibling combinator" (+).
  - *Selector*: + ul
- **Individual Change Selector (within list):**
  - *Description*: The selector for each `<li>` element within the list of changes.
  - *Selector*: li 