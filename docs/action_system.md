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
| RESTORE | RESTORE \[Target\] \[Resource\] \[Amount\] | Refills a resource (STAMINA or MANA) up to its maximum. Characters without that resource are unaffected. |
| CLEANSE | CLEANSE \[Target\] \[Status Name \| ALL\_DEBUFFS\] | Removes a named status. ALL\_DEBUFFS removes every status whose definition is tagged `debuff`, plus all negative stat modifiers. |

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
| **Positional** | \[Position\] \[Target\] | Selects based on battlefield position relative to a specific target. **Position** can be LEFT\_OF, RIGHT\_OF, ADJACENT\_TO. **Target** must be a specific reference. Example: ADJACENT\_TO SPECIFIC\_TARGET target1.1. *Not yet supported: there is no battlefield position model, so the parser rejects these with an `unsupported` error.* |

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

### **5\. Engine Semantics**

These rules define how the engine (`src/systems/actions/`) interprets the syntax above. They are covered by the test suite.

**Grammar**

```
line      := [DELAY mode unit amount] [IF condition] COMMAND target params*
target    := selector [CHOICE|RANDOM] [filters] [CHOICE|RANDOM]
filters   := filter ((AND|OR) filter)* , with NOT and ( ) allowed; precedence NOT > AND > OR
condition := clause ((AND|OR) clause)* , with NOT and ( ) allowed
clause    := target | LAST_ACTION <action filters> | ABILITY <id> IS_READY
```

* **Parameters are single whitespace-free tokens.** `1.5*STR` and `2d10+INT` are valid; `1.5 * STR` is not. Each filter has a fixed number of arguments (for example, `WITH_STAT` takes 3), which is how the parser knows where the targeting phrase ends and the parameters begin.
* **Chaining clauses.** An `AND` or `OR` followed by a subject keyword (`SELF`, `PLAYER`, `LAST_ACTOR`, `LAST_ACTION`, `ABILITY`, a back-reference, or a base selector) starts a new clause. Otherwise it joins filters inside the current clause. `SELF WITH_TAG a AND WITH_TAG b` is one clause; `LAST_ACTOR IS_PLAYER AND LAST_ACTION ACTION_HAS_TAG spell` is two.
* **Line numbers** (for `SPECIFIC_TARGET` and `ALL_TARGETS_LINE`) count non-blank, non-comment lines from 1. Malformed lines still take a number. `#` starts a comment.
* **Malformed lines** are dropped with a diagnostic when data loads (see `DataLoader.validate()`). A line that fails at runtime, for example by dividing by zero, is skipped with a warning.

**Amounts.** A token is resolved as an integer first, then as a **range** if it exactly matches `low-high` (e.g. `20-30`, rolled uniformly), and otherwise as a **formula**. To subtract numbers, use a formula such as `(30-20)`. Formulas support `+ - * / **`, parentheses, dice atoms (`2d10`, rolled per target), stats of the caster (case-insensitive, with aliases `HP`, `MAX_HP`, `hp_percentage`, `STAMINA`, `MANA`), and `PREVIOUS_DAMAGE_DEALT` (the total from the most recent `DAMAGE` line in this action). Results are floored to integers.

**Targeting.** The candidate pool is built first, then filters are applied, then the quantity is selected.

* Groups are relative to the caster. `ALLY` includes the caster.
* Dead characters are never targeted.
* Selection never picks the same character twice. If the pool is no larger than the quantity, every character in it is taken.
* When no mode is given, the mode is `RANDOM`.
* With `CHOICE`, the player is prompted. An AI caster instead applies a policy chosen by verb, which an action can override with an `"ai_target"` field: `HEAL` targets the lowest health %; `DAMAGE`, `DEBUFF` and `APPLY` target the lowest current HP; other verbs target the caster first.

**Conditions.** A target clause is true when at least one character survives its filters; quantity and mode are ignored. `WITH_STAT` falls back to the character's variables when the name is not a stat. A missing variable compares as null, so only `!=` can be true against it. Every action automatically gets a tag for where it was defined: `technique`, `spell`, `item`, or `basic` (the built-in Attack, Defend and Run).

**Durations and cooldowns.** All `N_TURNS` timers follow one rule:

* The timer belongs to the character it affects (the bearer).
* It counts down at the end of the bearer's turn.
* It does not count down during the turn in which it was applied.
* It expires when it reaches 0.

So `BUFF SELF DEFENSE 10 1_TURN` lasts through the enemies' actions until the end of the caster's next turn.

`ROUNDS` and `TIME_UNITS` timers use the combat clock instead. One round is `round_time_units / reference_speed` (12500 / 125 = 100) time units.

Singular and plural units (`1_TURN`, `3_TURNS`) and dice (`1d3_ROUNDS`) are accepted. Combat-scoped state is cleared when combat ends; only variables set without a duration persist.

**DELAY.**

* `DELAY … TURNS N` fires at the start of the caster's N-th later turn, before status effects tick and before the caster acts. The caster then still takes that turn.
* `ROUNDS` and `TIME_UNITS` delays fire when the clock reaches their due time.
* The line's `IF` condition and its targets are evaluated when it fires, not when it is queued.
* `BLOCKING` resumes the remaining lines right after the delayed line fires. `NONBLOCKING` queues the line and continues immediately.
* If the caster dies, its pending delayed lines are cancelled.

**Damage.** Each hit is resolved in this order:

1. Evaluate the amount.
2. Apply the `<type>_resistance` stat as a percentage. Resistance is clamped to the range −100 to 90.
3. Subtract `DEFENSE`. This step applies to `PHYSICAL` damage only.
4. Deal a minimum of 1 damage for any positive hit.

**Statuses** are defined in `data/statuses.json` with:

* `stacking`: `refresh`, `stack` or `ignore`.
* `tags`.
* `hooks`: action strings run with the bearer as `SELF`, once per stack. The available hooks are `on_apply`, `on_turn_start`, `on_turn_end`, `on_damage_taken` and `on_expire`.

Applying a status name that has no definition is allowed; it acts as a plain marker (e.g. `ritual_mark`).

**Predefined Actions** are referenced from data as `"predefined_action": {"name": "...", "params": {...}}` and implemented with `@register_predefined`. New verbs and filters are added with `@register_command` and `@register_filter`.

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