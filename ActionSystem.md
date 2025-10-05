# **Action System Pseudo-Code Design Document**

This document outlines the syntax for the action\_string used by abilities and spells. The game's combat engine will parse these strings to execute actions. This is a technical reference.

### **Core Line Structure**

Each line in an action\_string follows a consistent format:  
\[LINE\_MODIFIERS\] COMMAND \[TARGETING\_PHRASE\] \[PARAMETERS\]

### **1\. Line Modifiers**

Optional keywords that prepend a line to alter its fundamental execution rules. When both modifiers are used on the same line, DELAY must always come before IF.

| Keyword | Syntax | Description |
| :---- | :---- | :---- |
| IF | IF \[Targeting Phrase\] | A conditional gate. The rest of the line will only execute if the condition is met. The \[Targeting Phrase\] is evaluated, and if it results in one or more valid targets, the condition is considered true. For example, IF SELF WITH\_TAG goblin\_kin checks if the caster has that tag. |
| DELAY | DELAY \[Mode\] \[Unit\] \[Amount\] | Delays the line's execution. **Mode** must be BLOCKING (halts the processing of all subsequent lines in this action) or NONBLOCKING (queues this line for later and continues to the next line immediately). **Unit** can be TIME\_UNITS, TURNS, or ROUNDS. **Amount** is a number. The effect triggers at the *end* of the specified duration. |

### **2\. Commands**

The primary verb of the line, defining the core effect.

| Keyword | Syntax & Parameters | Description |
| :---- | :---- | :---- |
| DAMAGE | DAMAGE \[Target\] \[Amount\] \[Type\] | Inflicts damage. **Amount** can be a number, dice, or formula. **Type** is a damage type (e.g., PHYSICAL, FIRE). |
| HEAL | HEAL \[Target\] \[Amount\] | Restores health. **Amount** can be a number, dice, or formula. |
| BUFF | BUFF \[Target\] \[Stat\] \[Amount\] \[Duration\] | Temporarily increases a stat. **Stat** is a character stat (e.g., STR). **Amount** is the value to add. **Duration** is how long it lasts (e.g., 3\_TURNS). |
| DEBUFF | DEBUFF \[Target\] \[Stat\] \[Amount\] \[Duration\] | Temporarily decreases a stat. Functionally identical to BUFF with a negative amount. |
| APPLY | APPLY \[Target\] \[Status Name\] \[Duration\] | Applies a named status effect. **Status Name** is a string (e.g., POISON). **Duration** is how long it lasts. |
| SET | SET \[Target\] \[Var Name\] \[Value\] \[Duration\] | Sets a custom variable on a target. **Var Name** is a string. **Value** can be a number, string, or boolean. **Duration** is optional; if omitted, the variable is permanent until removed. |

### **3\. Targeting Phrase**

The most complex component, defining *who* is affected. It is composed of **Selectors** and **Filters**.

#### **3.1. Target Selectors**

These keywords establish the initial pool of potential targets.

| Selector Keyword | Syntax | Description |
| :---- | :---- | :---- |
| **Base Selector** | \[Quantifier\]\_\[Group\] | The most common selector. **Quantifier** is a number (1), ALL, or dice (1d3). **Group** is SELF, ALLY, or ENEMY. Examples: 1\_ENEMY, ALL\_ALLIES. |
| CHOICE | ... CHOICE | A modifier for a Base Selector. If multiple targets are possible, prompts the player to choose. Example: 2\_ENEMIES CHOICE. |
| RANDOM | ... RANDOM | A modifier for a Base Selector. If multiple targets are possible, chooses them randomly. Example: 1\_ALLY RANDOM. |
| SPECIFIC\_TARGET | SPECIFIC\_TARGET target\<L\>.\<I\> | References a single, specific target from a previous line. L is the line number, I is the target's index on that line. Example: SPECIFIC\_TARGET target1.1. |
| ALL\_TARGETS\_LINE | ALL\_TARGETS\_LINE\<L\> | References all targets from a specific previous line L. Example: ALL\_TARGETS\_LINE2. |
| PREVIOUS\_TARGETS | PREVIOUS\_TARGETS | A convenient alias for ALL\_TARGETS\_LINE\<L-1\>, referencing all targets from the immediately preceding line. |
| ALL\_TARGETS\_SO\_FAR | ALL\_TARGETS\_SO\_FAR | References every unique character targeted by any previous line in this action string. |
| **Positional** | \[Position\] \[Target\] | Selects based on battlefield position relative to a specific target. **Position** can be LEFT\_OF, RIGHT\_OF, ADJACENT\_TO. **Target** must be a specific reference. Example: ADJACENT\_TO SPECIFIC\_TARGET target1.1. |

#### **3.2. Logical Filters**

These keywords are appended to a selector to refine the target list. They support parentheses () and logical operators AND, OR, NOT.

| Filter Keyword | Syntax | Description |
| :---- | :---- | :---- |
| WITH\_TAG | ... WITH\_TAG \[Tag Name\] | Filters for targets that possess the specified tag. Example: ALL\_ENEMIES WITH\_TAG undead. |
| WITH\_STAT | ... WITH\_STAT \[Stat\] \[Op\] \[Value\] | Filters based on a stat comparison. **Op** is a comparison operator (\>, \<, \=, \!=, \>=, \<=). **Value** can be a number or percentage. Example: ... WITH\_STAT HP \< 50%. |
| HAS\_STATUS | ... HAS\_STATUS \[Status Name\] | Filters for targets currently affected by a specific status. Example: ... HAS\_STATUS POISON. |
| EXISTS\_VARIABLE | ... EXISTS\_VARIABLE \[Var Name\] | Filters for targets that have a specific variable set on them. To check a value, use WITH\_STAT syntax with the variable name, e.g. ... my\_var \= true. Assumes non-existent variables return a null-equivalent value. |

### **4\. Parameters**

The arguments that provide details for commands (e.g., damage amount, duration).

| Parameter Type | Format | Examples |
| :---- | :---- | :---- |
| **Amount/Value** | Number, Dice, Range, Formula | 25, 3d6, 20-30, 1.5\*STR, PREVIOUS\_DAMAGE\_DEALT |
| **Damage Type** | String constant | PHYSICAL, FIRE, ICE, POISON, HOLY, DARK |
| **Stat Name** | String constant | STR, DEX, CON, INT, WIS, CHA, DEFENSE, SPEED |
| **Duration** | Number \+ Unit | 3\_TURNS, 1d3\_ROUNDS |

### **Comprehensive Examples**

* **Ritual of Sacrifice (BLOCKING):**  
  APPLY SELF ritual\_mark 3\_TURNS  
  DELAY BLOCKING TURNS 3 IF SELF HAS\_STATUS ritual\_mark DAMAGE ALL\_ENEMIES 200 DARK  
  HEAL SELF 100

  *Description: The caster marks themself. The second line is queued to execute after 3 turns, but BLOCKING stops the parser. The HEAL on the third line will **only** execute after the 3-turn delay is over and the damage line has been resolved. This is a powerful, delayed combo where the caster is rewarded after the main effect goes off.*  
* **Defensive Charge (NONBLOCKING):**  
  SET SELF is\_charging true 1\_TURN  
  DELAY NONBLOCKING TURNS 1 IF SELF EXISTS\_VARIABLE is\_charging DAMAGE 1\_ENEMY CHOICE 5d10 SHOCK  
  BUFF SELF DEFENSE 50 1\_TURN

  *Description: The caster sets a variable on themself. The second line is queued for next turn, but NONBLOCKING allows the parser to immediately continue to the third line. The caster gets the DEFENSE buff on the **current turn**, protecting them while they charge the attack. This demonstrates queuing a delayed effect while other parts of the ability resolve instantly.*