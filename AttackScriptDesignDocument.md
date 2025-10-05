# **AI Attack Script Design Document**

## **1\. Overview**

The Attack Script system is a data-driven AI engine that allows for the creation of complex and varied enemy behaviors without writing new code. Each enemy's logic is defined by one or more "Attack Scripts" in their JSON file. This document specifies the structure and syntax for writing these scripts.

## **2\. Attack Script JSON Structure**

An enemy's AI is defined by a list of attack\_scripts objects. Each object represents a distinct behavioral pattern.

"attack\_scripts": \[  
  {  
    "activation\_condition": "IF SELF WITH\_STAT hp\_percentage \> 50",  
    "interruptible": true,  
    "script\_lines": \[  
      "..."  
    \]  
  },  
  {  
    "activation\_condition": "IF SELF WITH\_STAT hp\_percentage \<= 50",  
    "interruptible": false,  
    "script\_lines": \[  
      "..."  
    \]  
  }  
\]

### **Components**

* **activation\_condition**: An IF statement that determines if the script is valid. It uses the exact same powerful filtering syntax defined in the action\_system\_design.md.  
* **interruptible**: A boolean.  
  * true: The AI will re-evaluate all script conditions at the start of its turn. This allows an enemy to dynamically change tactics based on the flow of battle.  
  * false: The AI is "locked in" to this script and must complete a full loop (execute every line once) before it can re-evaluate conditions and potentially switch to another script.  
* **script\_lines**: An ordered list of strings, where each string defines the action(s) to be taken on a specific turn.

## **3\. Script Selection and Execution**

### **Selection Logic**

At the start of an enemy's turn, the AI controller follows these steps:

1. It checks if the current, active script is interruptible: false. If so, it skips to Execution.  
2. It evaluates the activation\_condition for every script in its list, in order.  
3. The **first script** whose condition evaluates to TRUE becomes the active script.  
4. If the active script has changed, **its execution always starts from the first line (line 0\)**.  
5. If no condition is met, the first script in the list is chosen as a fallback.  
6. If an enemy has no scripts defined, its default behavior is to **randomly select and use one of its abilities that is not currently on cooldown.**

### **Execution Flow**

Once a script is active, the AI executes one valid line per turn, looping back to the beginning after the last line is complete. Any blank or malformed lines in the script are skipped entirely and do not consume a turn in the script's execution sequence. For example, a script with action1, a blank line, then action2 is a two-turn script.

## **4\. Script Line Syntax**

Each line in script\_lines is a complete statement that determines the AI's action for that turn.

### **4.1. Basic Actions**

Single Action  
The simplest form, instructing the AI to use a specific ability.

* **Syntax:** use\_ability \<ability\_name\_or\_id\>  
* **Example:** use\_ability fireball

Weighted Random Action  
Guarantees one action is chosen from a list based on weights.

* **Syntax:** WEIGHTED\_CHOICE { WEIGHT \<w1\>: \<action1\> } { WEIGHT \<w2\>: \<action2\> } ...  
* **Example:** WEIGHTED\_CHOICE { WEIGHT 70: use\_ability sword\_slash } { WEIGHT 30: use\_ability pommel\_strike }

Probabilistic Line  
Uses the CHANCE modifier. If the CHANCE evaluates as FALSE, the line inside its braces {} is treated as if it's blank. Because blank lines are skipped, this makes the entire line's execution probabilistic.

* **Syntax:** CHANCE \<0-100\> { \<action\_line\> }  
* **Example:** CHANCE 25 { use\_ability quick\_jab }

### **4.2. Conditional Logic**

Any script line can be made conditional using an IF/ELSE IF/ELSE structure. This allows for highly reactive and intelligent behavior within a single turn of a script. The condition is checked first; if it fails, the entire line (or block) is skipped.

* **Syntax:** IF \<condition\> { \<action\_if\_true\> } \[ELSE IF \<condition2\> { \<action2\> }\] \[ELSE { \<action\_if\_false\> }\]  
* **The \<condition\> uses the full power of the Action System's targeting and filtering engine.**

### **4.3. AI-Specific Keywords for Conditions**

To make intelligent decisions, the AI's conditional logic can use special keywords to query the state of the battle.

**Contextual Selectors:**

* PLAYER: A direct selector for the player character.  
* LAST\_ACTOR: The character who performed the most recent action.  
* LAST\_ACTION: The ability/spell that was just used.

Contextual Filters:  
These are used to query the properties of the contextual selectors.

* ACTION\_HAS\_TAG \<tag\>: Checks if an action has a specific tag.  
* IS\_PLAYER: Checks if a character is the player.  
* ALLY\_COUNT \<operator\> \<value\>: Checks the number of allies a character has.  
* ENEMY\_COUNT \<operator\> \<value\>: Checks the number of enemies a character has.

**Ability State Filters:**

* **ABILITY \<ability\_name\> IS\_READY**: Checks if the specified ability is currently usable (i.e., not on cooldown). This is the primary mechanism for scripts to respect cooldowns.

### **4.4. Examples of Conditional Script Lines**

Simple Retaliation:  
If the player just cast a spell, the goblin retaliates with a thrown knife.

* IF LAST\_ACTOR IS\_PLAYER AND LAST\_ACTION ACTION\_HAS\_TAG spell { use\_ability knife\_throw }

Calling for Help:  
If the goblin has no allies left, it uses a turn to summon help; otherwise, it attacks.

* IF SELF ALLY\_COUNT \= 0 { use\_ability summon\_imp } ELSE { use\_ability desperate\_strike }

Cooldown Management:  
A monster tries to use its powerful breath weapon if it's available; otherwise, it uses a basic claw attack.

* IF ABILITY dragon\_breath IS\_READY { use\_ability dragon\_breath } ELSE { use\_ability claw\_swipe }