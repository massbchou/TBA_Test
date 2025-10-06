# **Game Design Document: Project Roguelike**

## **1\. High-Concept**

Project Roguelike is a turn-based, text-based, single-player adventure game. The player progresses through an infinite series of procedurally generated levels, encountering random events, engaging in tactical combat, and continually upgrading their character. The core of the game is its deep data-driven architecture, allowing for complex and emergent interactions through a powerful custom action system.

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
* Saving and loading functionality is handled by helper functions in utils.py.

## **3\. The Player Character**

### **Stats**

The player character is defined by a robust set of statistics, mirroring the classic TTRPG format. All character data is stored and loaded via JSON files.

* **Primary Stats:** Strength (str), Dexterity (dex), Constitution (con), Intelligence (int), Wisdom (wis), Charisma (cha).  
* **Derived Stats:** Defense, Max Health, Stamina, Mana, Speed, Luck. These are visible to the player at all times.  
* **Hidden Stats:** A set of internal stats not normally visible, such as Fire Resistance or Regeneration Rate. By default, these are zero but can be modified by events or abilities.

### **Leveling & Experience**

The player gains Experience (EXP) by completing events, primarily combat. Upon reaching an EXP threshold, the player levels up. The EXP required for the next level is determined by a configurable algorithm.

* **Level Up Benefits:** When a player levels up, they are presented with a choice of randomly drawn perks or stat increases, pulled from tiered pools.

### **Inventory & Resources**

The player character tracks two primary resources:

* **Gold:** The main currency, used for shops and other events.  
* **Inventory:** A list of items the player possesses.

*(TODO: Define the structure for items in the inventory and create a system for using them, both in and out of combat.)*

### **Technical Implementation Notes**

* The Player class in player.py inherits from the base Character class and adds EXP, gold, and inventory management.  
* The EXP-to-level formula is defined in settings.json as a string formula (e.g., `player.experience_to_level_formula: "100 * (1.1 ** (level - 1))"`).
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

### **Abilities & AI**

Enemies do not use a basic attack. Their entire behavior is dictated by a list of abilities and spells they can use. For simplicity, enemies do not consume Mana or Stamina; instead, their abilities have turn-based cooldowns. The cooldown duration for an ability can be specific to the enemy using it. An enemy's AI is governed by a programmable **Attack Script** system, detailed in Section 8\.

### **Loot**

Defeated enemies drop loot based on a loot\_table. Each entry in the table has a chance to drop, and if successful, yields a quantity between min\_amount and max\_amount. An enemy can drop multiple types of loot from a single kill.

### **Technical Implementation Notes**

* The Enemy class in character.py inherits from the Character base class.  
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
   * **Rest:** A special event that allows the player to recover Health, Mana, and Stamina. It will also feature a shop.

*(TODO: Implement the shop functionality within the Rest event.)*

### **Technical Implementation Notes**

* The EventManager class (event\_manager.py) is the brain of this system.  
* It uses complex, nested weighted distributions defined in `settings.json` to generate event choices. This includes separate weightings for `regular` and `mystery` events (e.g., `events.distributions.regular.type_weights`).
* It generates combat encounters based on level-tiered rules, which specify enemy tags and weighted enemy counts (e.g., `combat.encounter_generation.regular_combat_rules_by_tier`).
* Odds are calculated from weights, not percentages that must sum to 1, for easier configuration.  
* Event definitions are stored in `data/events.json` and are filtered using tags.
* The `events.py` file contains the Python classes that represent and execute the logic for each event type (e.g., CombatEvent, OccurrenceEvent), including subtypes for "Ordeal" and "Boss" encounters.

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

*(TODO: Define the specific mechanics for the Defend, Technique, Item, and Run actions. Currently, only a generic action exists.)*

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
* The Enemy class in character.py will need attributes to track AI state (current\_script\_index, current\_script\_line).  
* A new AIController module should be created to manage all AI logic.  
* The AIController will parse and execute the script lines, using the same IF condition evaluator built for the Action System.  
* Malformed script lines are ignored with a warning.