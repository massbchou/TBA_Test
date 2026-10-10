# **Game Design Document: TextRogue**

## **1\. High-Concept**

TextRogue is a turn-based, text-based, single-player adventure game. The player progresses through an infinite series of procedurally generated levels, encountering random events, engaging in tactical combat, and continually upgrading their character. The core of the game is its deep data-driven architecture, allowing for complex and emergent interactions through a powerful custom action system.

## **2\. Core Game Loop & Progression**

### **Game Flow**

The player's journey is structured into a sequence of **Levels**. Each Level consists of a single **Event**. After successfully completing an Event, the player is presented with a choice of several potential Events for the next Level. By default, they can choose from two known events and one "mystery" event.

At the end of each event, the player has the option to save their progress to a JSON file and exit the game. The game is designed for infinite play, with difficulty scaling over time.

### **Boss Encounters**

Boss encounters are special, challenging events that occur at fixed intervals, serving as milestones and the culmination of an event "tier". A tier is a conceptual grouping of Levels (e.g., Levels 1-9 are Tier 1, with Level 10 being the Tier 1 Boss).

*(TODO: Define the specific mechanics for difficulty scaling. This could involve increasing enemy stats, introducing more complex enemy compositions, or adding environmental modifiers.)*

### **Technical Implementation Notes**

* The main game loop is managed in main.py.  
* A GameState class (game\_state.py) tracks the current level number, player data, and other session-wide information.  
* The EventManager class (event\_manager.py) is responsible for generating the choices for the next event, based on rules in settings.json.  
* The number of event choices (next\_event\_choices) and mystery options (mystery\_choices) are defined in settings.json.  
* The boss encounter rate (boss\_event\_interval) is also set in settings.json.  
* Saving and loading is handled by `src/save_manager.py`: the camp menu offers "Save and quit", which writes `saves/<name>.json` (player, floor, event history and RNG state). A finished run deletes its save.
* Between floors the **camp** (`src/systems/camp.py`) lets the player use items and camp-usable skills, review their character, or save and quit.

## **3\. The Player Character**

### **Stats**

The player character is defined by a robust set of statistics, mirroring the classic TTRPG format. All character data is stored and loaded via JSON files.

* **Primary Stats:** Strength (str), Dexterity (dex), Constitution (con), Intelligence (int), Wisdom (wis), Charisma (cha).  
* **Derived Stats:** Defense, Max Health, Stamina, Mana, Speed, Luck. These are visible to the player at all times.  
* **Hidden Stats:** A set of internal stats not normally visible, such as Fire Resistance or Regeneration Rate. By default, these are zero but can be modified by events or abilities.

**What each stat does:**

| Stat | Used by |
| :---- | :---- |
| STR | Basic Attack (Warrior, Priest; part of the Mage's), Warrior techniques, Rebuke, Collector's Strike, enemy physical attacks |
| DEX | Martial Artist's Attack and techniques, Collector's Strike |
| CON | **Max HP** (`base_hp + 6 × CON`, plus any bonus HP) and Max Stamina (`40 + 5 × (CON − 10)`) |
| INT | Mage spells, Max Mana (except the Priest's), enemy spells |
| WIS | Priest heals, Smite, Renewal, the Priest's Max Mana |
| CHA | Shop discount (2% per point above 10, up to 25%) |
| Defense | Flat reduction of physical-type damage (PHYSICAL, SWORD, STAFF) |
| Speed | Turn frequency |
| Luck | Currently unused |

Max HP is derived: changes to it from perks or events (e.g. Stout Heart) go to a separate **bonus HP** stat, and raising CON raises both maximum and current HP.

### **Leveling & Experience**

The player gains EXP from winning fights and from some events. A fight's EXP is `combat.exp_formula` of each enemy's **level** (`15 + 8 × level`), multiplied by its category: Elite ×2.5, Boss ×5. Event EXP can scale with the floor (e.g. `10 + 6 × floor`). The EXP needed for the next level is `player.exp_formula` (`50 × 1.25^(level − 1)`). Leftover EXP carries over, so one fight can give several levels.

**Each level-up**, in order:

1. **Random stat points.** The number of points N is drawn from a flattened bell centred on the new level: half the time it is uniform between the floor (1) and 2 × level, otherwise a normal draw with a standard deviation of 0.6 × level. N is never below the floor. Each point lands on one of the six primary stats, weighted by the class's `stat_weights`. The bias fades as N rises above the floor (`weight ^ (1 / (1 + (N − 1) / level))`): small rolls go to class stats, big rolls spread across all six.
2. **Full heal:** HP, Stamina and Mana are restored to full.
3. **Perk choice** (none after the final fight).

* **Level Up Benefits:** The perk choice is drawn from tiered pools. One choice is offered per level gained. The pool used is the highest `tierN` whose N is at most `ceil(level / boss_level_interval)`. A perk marked `"repeatable": false` is never offered again once taken. Perks and occurrence choices share one effect system (`src/systems/effects.py`).

### **Inventory & Resources**

The player character tracks two primary resources:

* **Gold:** The main currency, spent at waystation shops (CHA lowers prices) and on paid event choices. Road thieves steal it; defeating them returns it.  
* **Inventory:** A list of items the player possesses.

**Items** are defined in `data/items.json` and work like abilities: each item has an `action_string` and a `usable_in_combat` flag. The inventory maps item ids to stack sizes. Using an item runs its action and removes one from the stack. Using items outside combat is not implemented yet.

**Stamina and Mana** are resources whose maximums come from formulas in `settings.json` (`player.derived_stats`), based on Constitution and Intelligence. Maximums are recalculated when base stats change. Resources carry over between combats and are fully restored at Rest stops. In combat, Stamina regenerates a small amount every turn (`combat.stamina_regen_per_turn`).

### **Technical Implementation Notes**

* The Player class in player.py inherits from the base Character class and adds EXP, gold, and inventory management.  
* The EXP-to-level formula is defined in settings.json (e.g., experience\_rate\_base, experience\_rate\_algorithm).  
* The data for starting character options is stored in data/starting\_classes.json.  
* The pool of potential level-up benefits is stored in data/level\_up\_perks.json.

## **4\. Enemies**

### **Enemy Definition**

Enemies share the exact same statistical structure as the player. However, by default, only their Health is visible to the player in combat. Enemies are defined in JSON data files and are selected for combat using a tag-based system.

### **Categories**

Enemies are grouped into four main categories, which dictates how they are used in events:

* **Normal:** Standard enemies found in regular combat.  
* **Elite:** More powerful enemies with unique abilities, found in Ordeal events.  
* **Boss:** The most powerful enemies, appearing only in designated Boss events.  
* **Special:** Reserved for unique, scripted encounters.

### **Levels and Scaling**

An enemy's data `level` is its **base level**, and its `stats` are its stats at that level. Its **spawn level** comes from the floor, using the first of these that applies:

1. An event's `levels` map for that enemy (boss events fix the bosses at 10).
2. The floor band's `enemy_levels` map.
3. The floor band's `level_range`.
4. Otherwise, the floor ±1 (`combat.enemy_level_variance`).

Stats scale linearly from the base level: `base × max(0.4, 1 + rate × (level − base_level))`. The default rates are +8% Max HP, +5% STR/DEX/INT/WIS, +3% Defense and +1% Speed per level. A family can grow faster in chosen stats with `growth` (Ash Wolves gain speed, Dusk-Touched Knights gain defense, Mire Toads gain HP). Resistances don't scale. Levels are shown on the path choices and in combat.

### **Abilities & AI**

Enemies do not use a basic attack. Their entire behavior is dictated by a list of abilities and spells they can use. For simplicity, enemies do not consume Mana or Stamina; instead, their abilities have turn-based cooldowns. The cooldown duration for an ability can be specific to the enemy using it. An enemy's AI is governed by a programmable **Attack Script** system, detailed in Section 8\.

### **Loot**

Defeated enemies drop loot based on a loot\_table. Each entry in the table has a chance to drop, and if successful, yields a quantity between min\_amount and max\_amount. An enemy can drop multiple types of loot from a single kill.

### **Technical Implementation Notes**

* The Enemy class in models/enemy.py inherits from the Character base class.  
* All enemy definitions are stored in data/enemies.json.  
* Each enemy object has a tags array, which the EventManager uses for filtering when constructing combat events.  
* The abilities list on an enemy object contains references to abilities and their specific cooldown rules.  
* Loot processing logic exists in the Combat class in combat.py.

## **5\. The Event System**

### **Event Structure**

Events are the core content of the game, divided into five Tiers by default, corresponding to game levels. The system is designed to support any number of tiers. Events are defined in JSON data and selected by the EventManager based on weighted odds.

### **Event Types & Subtypes**

1. **Combat Events:** Initiate a combat encounter.  
   * **Regular Combat:** A battle against 1 or more "Normal" enemies, with composition determined by weighted distributions for the current level range.  
   * **Ordeal:** An event that can either be a pre-constructed, specific encounter (e.g., "Goblin Ambush") or a randomly generated battle featuring "Elite" enemies.  
   * **Boss Combat:** A battle against a single, powerful "Boss" enemy appropriate for the current tier.  
2. **Occurrence Events:** Text-based scenarios that require player choice.  
   * **Normal & Reward:** Present the player with a description and a numbered list of options. The pools of events are separate, with "Reward" occurrences generally offering better outcomes. These events can feature nested choices.  
   * **Rest:** A special event that allows the player to recover Health (a fraction set by `combat.rest_heal_fraction`) and fully restore Mana and Stamina. It will also feature a shop.

Rest stops (waystations) offer **Rest**, which uses up the stop, and **Trade** with a merchant: buy at full price (minus a CHA discount) and sell at half. The floor before a boss always offers a rest stop.

### **Technical Implementation Notes**

* The EventManager class (event\_manager.py) is the brain of this system.  
* It uses weighted distributions defined in settings.json (event\_type\_distribution, combat\_composition\_by\_level, etc.) to generate event choices.  
* Odds are calculated from weights, not percentages that must sum to 1, for easier configuration.  
* Event definitions are stored in data/events.json and are filtered using tags.  
* The events.py file contains the Python classes that represent and execute the logic for each event type (e.g., CombatEvent, OccurrenceEvent).

## **6\. Combat Mechanics**

### **Turn-Based System**

Combat is resolved in a turn-based manner on a continuous time scale. A **Round** is a conceptual block of 125 time units. A character's **Speed** stat determines how quickly they accumulate action time. A character with 125 Speed acts roughly once per round, while a character with 250 Speed acts twice. The character with the lowest accumulated action\_time takes the next turn.

### **Player Actions**

The player has six primary action types they can take on their turn. These foundational actions will be implemented as **Predefined Actions** for efficiency and reliability.

1. **Attack:** Perform a basic or weapon-based strike.  
2. **Defend:** Take a defensive stance to mitigate incoming damage.  
3. **Technique:** Use a Stamina-costing physical ability.  
4. **Cast:** Use a Mana-costing spell.  
5. **Bag/Item:** Use an item from the inventory.  
6. **Run:** Attempt to flee combat.

Attack, Defend and Run are built-in Predefined Actions:

* **Attack** deals `basic_attack` PHYSICAL damage. The formula is set per starting class (default `1.0*STR`).
* **Defend** grants `combat.defend_formula` DEFENSE (default `5+CON/2`) until the end of the player's next turn.
* **Technique and Cast** list the player's known abilities and spells with their costs. Choosing an option the player cannot afford, or choosing Back, returns to the menu without using up the turn.
* **Bag** lists items that can be used in combat.
* **Run** succeeds with probability `clamp(50 + (player speed − average enemy speed) × 0.5, 10, 90)`%. Fleeing grants no rewards but clears the floor. Running is not allowed in Boss fights. A failed attempt still uses up the turn.

Combat ends in one of three outcomes: VICTORY, DEFEAT or FLED.

### **Technical Implementation Notes**

* The Combat class in combat.py manages the entire combat loop, including the turn order algorithm.  
* The combat\_round\_time\_units value is set in settings.json.  
* Each character object has an action\_time attribute that is incremented after their turn. The turn cost is calculated based on their Speed.  
* All player and enemy actions are ultimately resolved through the Action System.

## **7\. The Action System**

### **7.1 Overview**

The Action System is a hybrid engine designed for maximum flexibility. It supports two distinct types of actions: dynamically parsed **Action Strings** and hard-coded **Predefined Actions**. This allows for the rapid creation of standard effects while also supporting unique, complex mechanics. An ability or spell in the JSON data must specify one type or the other.

### **7.2 Predefined Actions**

A Predefined Action is a direct call to a specific, hard-coded Python function. Instead of an action\_string, the ability's data file will specify a predefined\_action object, which includes the name of the function to call and any necessary parameters.

### **7.3 Action Strings**

This is the data-driven core of the system. The effects of most abilities and spells are defined by a multi-line, pseudo-code action\_string.

### **Technical Implementation Notes**

* **The definitive syntax for Action Strings is specified in Action System file.**  
* The ActionOrchestrator (action\_orchestrator.py) handles both Predefined Actions and Action Strings.  
* The Action String pipeline involves a Lexer, Parser, Target Resolver, and Command Executor.  
* Malformed lines are ignored with a warning.

## **8\. Enemy AI System**

### **8.1 Overview**

The Enemy AI is a programmable, data-driven system. Each enemy's behavior is defined by a list of one or more **Attack Scripts** in their JSON definition. This allows for creating varied and dynamic behaviors, from simple attack patterns to complex, multi-phase boss fights.

The system is governed by a set of rules for how scripts are selected and executed based on the state of combat. This allows enemies to change tactics when their health is low, when allies are defeated, or in response to player actions.

### **Technical Implementation Notes**

* **The complete syntax and logic for writing Attack Scripts is specified in the Attack Script document.**  
* The Enemy class (models/enemy.py) tracks AI state in an AIState object (current\_script, line, locked).  
* A new AIController module should be created to manage all AI logic.  
* The AIController will parse and execute the script lines, using the same IF condition evaluator built for the Action System.  
* Malformed script lines are ignored with a warning.