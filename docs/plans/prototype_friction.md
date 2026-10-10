# Prototype Friction Log: Octopath Traveler Content Pass

**Date:** 2026-10-10 · **Branch:** `feat/octopath-prototype-content`

## Goal

Populate the engine with a first-pass game inspired by *Octopath Traveler* (2018). Then find where the
engine and data formats are clunky by **authoring content without changing the engine**.

Content was written only as JSON. Anything the data could not express is logged here, not worked
around in code.

## What was built

| Area | Content |
|:---|:---|
| Classes (8) | Warrior, Hunter, Cleric, Scholar, Merchant, Thief, Apothecary, Dancer. Each class has Octopath-style kits and weapon/element identities (e.g. Level Slash, Rain of Arrows, Heal Wounds, Icicle, Tradewinds, HP Thief, First Aid, Moonlight Waltz). |
| Enemies (10) | 5 normal (Ruffian, Sand Lizard, Giant Bat, Shroomling, Lizardman), 3 elite (Lizardman Chief, Bandit Captain, Hellhound), 2 bosses (Guardian of the First Flame, Blotted Viper). Each has weapon/element weaknesses and an attack script. |
| Items (8) | Healing Grape (single and bunch), Inspiriting Plum, Energizing Pomegranate, Herb of Healing, and Fire, Ice and Lightning Soulstones. |
| Statuses | POISON (deals % of max HP), REGEN. |
| Events | 7 occurrences themed on Octopath towns and path actions: Inquire, Purchase, Steal, Allure, Provoke, and others. 2 preconstructed ordeals. 2 boss events. |
| Perks (8) | Named after Octopath support skills, approximated as stat changes. |

The previous goblin/troll content now lives in `tests/fixtures/` and is used by the engine tests, so
editing game content can no longer break them.

### How Octopath's systems were mapped

- **Weaknesses** map to negative resistances (`sword_resistance: -50` → 1.5× damage). This works well.
- **Weapon types** (SWORD, SPEAR, DAGGER, AXE, BOW, STAFF) became damage types, used alongside the
  elements (FIRE, ICE, LIGHTNING, WIND, LIGHT, DARK).
- **Boss telegraphs** (Gathering Inferno) use `SET` plus `DELAY NONBLOCKING`, the same pattern as the
  spec's Defensive Charge example.
- **Drain** (HP Thief, Blood Drain) uses `HEAL SELF PREVIOUS_DAMAGE_DEALT/2`. This works well.

## Playtest results

The harness ran 300 seeded runs per class, floors 1–10, under three play styles. To reproduce:

```bash
python3 tools/playtest.py --policy {attack|random|heuristic} --runs 300
```

Clear rate is the share of runs that beat the floor-10 boss.

| Class | Attack only: avg floor | Random: avg floor | Heuristic: avg floor | Heuristic: boss reached | Heuristic: clear rate |
|:---|---:|---:|---:|---:|---:|
| Warrior | 5.8 | 6.7 | 9.5 | 86% | **0%** |
| Hunter | 5.3 | 6.4 | 9.5 | 88% | 25% |
| Cleric | 2.4 | 3.6 | 5.2 | 11% | **0%** |
| Scholar | 2.2 | 4.4 | 7.7 | 37% | **0%** |
| Merchant | 4.3 | 5.4 | 9.0 | 73% | **0%** |
| Thief | 5.1 | 6.1 | 9.4 | 87% | **0%** |
| Apothecary | 4.8 | 6.0 | 9.6 | 91% | 29% |
| Dancer | 4.3 | 4.7 | 8.0 | 47% | **0%** |

The heuristic player:
- heals below 40% HP;
- otherwise uses an affordable damaging skill;
- refills resources with items;
- steers toward rest stops and occurrences when wounded.

Players reach the boss at **level 1–2**: of 260 Warrior boss fights, 157 were at level 1 and 103 at
level 2.

---

## Findings

Severity: **🔴 blocks a core Octopath mechanic** · **🟠 forces a clunky workaround** · **🟡 polish**.

### A. Engine expressiveness: what the data could not say

| # | Sev | Finding | Evidence | Suggested direction |
|:---|:---|:---|:---|:---|
| A1 | 🔴 | **No Break/Shield system.** Octopath's core loop (each hit on a weakness strips a shield; at 0 the enemy is Broken: it skips its turns and takes extra damage) cannot be expressed. There is no way to count hits, because `SET` only stores literals and there is no increment. No status can stop a character from acting. There is no damage-taken multiplier. | Enemies have only static weaknesses, so a weakness is just a 1.5× number. | An `ADD <target> <var> <amount>` verb (or a formula `SET`); an `on_damage_taken` hook that receives the damage type; a status flag `prevents_action`; a `damage_taken_multiplier` stat. |
| A2 | 🔴 | **No party.** One player against N enemies. `HEAL ALL_ALLIES`, Lion Dance, Sheltering Veil and every "buff the party" skill collapse to self-only. 1-vs-1 against a 240–260 HP boss is a slugfest, not a puzzle. | 0% boss clears for 6 of 8 classes. | A `Battle` already supports sides as lists; the player side needs several characters and the menu needs a per-character turn. This is the biggest structural change. |
| A3 | 🔴 | **No Boost Points.** There is no per-turn accumulating resource and no way to spend a variable amount to scale or repeat an action. | Not representable. | Generalise `stamina_regen_per_turn` into a per-resource regen map; add a `REPEAT N` line modifier or an action-level "boost" param that feeds a formula variable. |
| A4 | 🟠 | **Weapon type is conflated with "physical".** Defense applies only to the `PHYSICAL` type, so SWORD/SPEAR/AXE skills ignore enemy Defense entirely. Meanwhile the basic Attack is hard-coded `PHYSICAL`, so it can never hit a weapon weakness. | A Warrior's Level Slash (12.8 SWORD, bypasses Defense) barely beats Attack (16 − 6 Defense = 10). Enemies were authored as `PHYSICAL` to keep Defense meaningful, which is inconsistent with the players' skills. | Give damage a *category* (physical/magical) separate from its *type*, or list weapon types as physical in settings. Let `basic_attack` declare a damage type. |
| A5 | 🟠 | **Statuses can only run hooks.** Sleep, Silence, Blind (accuracy), Terror and Stun need a status to *restrict actions* or *affect hit chance*. There is no hit/miss or evasion at all (Merchant "Sidestep", support skill "Evasive Maneuvers"). | Shroomling "sleep spores" had to become a speed debuff; Evasive Maneuvers became +2 Defense. | Status flags consulted by `Combat` (`cannot_act`, `cannot_cast`); an optional accuracy/evasion step in the damage pipeline. |
| A6 | 🟠 | **No combat verbs for gold or items.** Steal, Collect, Hired Help (spend gold) and Concoct (combine items) have no verbs. | Merchant got a generic "Rest" technique; Thief has no Steal. | `GAIN_GOLD`, `GIVE_ITEM`, `CONSUME_ITEM` verbs. Each is a single `@register_command`. |
| A7 | 🟠 | **Enemy-only actions share the player namespace.** Enemy abilities live in `abilities.json` / `spells.json`, get tagged `technique` / `spell`, need an `e_` prefix to avoid collisions, and nothing stops a class from listing them. | 14 `e_*` entries mixed into player files. | `data/enemy_actions.json` with source `enemy`; validation rejects enemy actions in class kits. |
| A8 | 🟠 | **Derived stats are global.** `max_mana` comes from INT for every class, so a Cleric (WIS caster) or Dancer (CHA caster) needs an inflated INT to get a mana pool. | The Cleric's INT was set to 12 purely to give it 30 mana. | Allow a per-class `derived_stats` override in `starting_classes.json`. |
| A9 | 🟠 | **Perks can only change stats.** Octopath support skills are passives: HP Thief (drain on hit), Elemental Augmentation (+50% elemental damage), Inspiration (SP regen), Endless Items (chance not to consume). None can be expressed. | All 8 perks are flat stat bumps with borrowed names. | A perk effect that applies a *permanent* status (hooks persist across combats), plus percentage modifiers. |
| A10 | 🟡 | **No multi-stat buffs.** Sheltering Veil needs six `BUFF` lines, one per element. | `spells.json` → `sheltering_veil`. | Allow `BUFF SELF ALL_RESISTANCES 30 3_TURNS`, or let a stat list (`fire,ice,…`) be one token. |
| A11 | 🟡 | **`starting_classes` ignores `gold`.** The Merchant can't start rich. | `build_player` doesn't read a gold field. | Read `gold` (and any other `Player` field) from the class data. |

### B. Occurrences and progression

| # | Sev | Finding | Evidence | Suggested direction |
|:---|:---|:---|:---|:---|
| B1 | 🔴 | **Purchases have no gold check. This is an exploit.** Gold clamps at 0 but the item is still granted, and the message reads "You gain 0 gold." | Scholar with 0 gold buys a Fire Soulstone at the Rippletide stall and receives it. | Choice-level `requires` (`{"gold": 40}`, stat thresholds, class); unmet choices are hidden or disabled. |
| B2 | 🟠 | **No chance-based outcomes.** Octopath path actions (Steal, Allure, Inquire) succeed on a % roll that depends on level and class; here every choice is deterministic. | "Pick his pocket" always works. | `{"chance": 0.6, "success": [...], "failure": [...]}` on a choice. |
| B3 | 🟠 | **Occurrences can't start a fight.** Provoke and Challenge should trigger combat. | "Challenge him" just prints flavour text. | A `combat` effect type that runs `Combat` with listed enemies. |
| B4 | 🟠 | **Levelling is weak and slow.** There's no stat growth per level, only one perk, and players reach the boss at level 1–2. | Level-at-boss distribution above. | Per-class growth tables applied on level-up, and/or a faster EXP curve. |

### C. Combat UX and readability

| # | Sev | Finding | Evidence | Suggested direction |
|:---|:---|:---|:---|:---|
| C1 | 🟠 | **Menu offers empty categories.** A Warrior can pick Cast ("You don't know any spells") and a Scholar can pick Technique. Each is a dead end. The playtest harness looped forever on this; `tools/playtest.py` now caps choices per run. | Found while building the heuristic player. | Hide or disable categories with no usable entries. |
| C2 | 🟠 | **Status ticks aren't attributed.** A POISON tick prints right after the enemy's action, so it reads as part of that attack. | Blotted Viper fight log. | Prefix hook narration (`[Poison] Hero takes 11 damage`). |
| C3 | 🟠 | **Hidden state.** `SET` narrates nothing, so a boss's "Gathering Inferno" charge is invisible until it lands. Buff/debuff *expiry* is silent (only statuses announce wearing off). Turn order and speed changes are never shown. Weaknesses are invisible, so there's no Analyze. | Guardian of the First Flame. | Optional `"message"` field on actions; narrate modifier expiry; a turn-order preview line; an Analyze-style reveal. |
| C4 | 🟡 | **Flat Defense subtraction makes weak hits feel bad.** In Cleric runs, 12% of all hits (both sides) dealt exactly 1 damage. The Cleric's staff attack (6.4) against Defense 3–5 is the main source. | 1,447 of 12,393 hits (heuristic, 300 runs). | Percentage mitigation (e.g. `dmg × 100/(100+def×k)`) instead of subtraction. |

### D. Balance (data only, no engine change needed)

- **Bosses are a wall.** They have 240–260 HP and hit for 11–17 plus 8%-of-max-HP poison, against one
  level-1 character. Coverage is thin: each boss's weaknesses are hit by 1–2 classes. Fixing this mostly
  depends on A1, A2 and B4; in the meantime, trim boss HP to about 160.
- **Casters starve.** Mana never regenerates in combat, and rest stops are 5% of event rolls. The Scholar
  and Cleric run dry within 1–2 fights (Cleric average floor: 5.2 even with heuristic play). Consider mana
  regen, cheaper spells, or a higher rest weight.
- **Stamina carries over too.** Warriors arrive at the boss with 12/70 stamina. Consider refilling
  resources between fights, or a partial refill on victory.
- **Elites can appear on floor 1.** `rules_by_level_range` allows Elite ordeals at levels 1–5. The
  Lizardman Warband and Bandit Ambush are the leading non-boss killers.

## Recommended order

1. **B1** (exploit) and **C1** (dead-end menu): small, high value.
2. **A4** (damage category vs type) and **C2**/**C3** narration: cheap; they make the weakness game
   readable.
3. **A1** (Break) with **A5** (action-blocking statuses): together they unlock Octopath's core loop on
   the existing hook system.
4. **A2** (party) and **A3** (Boost): the large structural decisions. Decide whether the game is
   party-based before investing more in balance.
5. Balance pass (section D) once the above settle.
