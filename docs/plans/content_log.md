# Content Log

This log records content passes, playtest results, and what manual play found. Newest pass first.

---

## Pass 3: Progression rework (2026-10-10)

**Branch:** `feat/progression`

### What changed
- **Enemy levels.** An enemy's data `level` is its base level. Spawn level comes from the floor (event
  `levels` > band `enemy_levels` > band `level_range` > floor ±1). Stats scale per level, with family
  `growth` bonuses. Levels are shown on paths and in combat.
- **EXP** is `15 + 8 × level` per enemy (Elite ×2.5, Boss ×5). Some events also grant floor-scaled EXP.
- **Max HP** is derived as `base_hp + 6 × CON`, plus bonus HP from perks and events.
- **Level-ups** grant a random number of stat points (a flattened bell centred on the level, with a
  minimum of 1). The class bias fades on big rolls. Every level-up fully restores HP, Stamina and Mana.

### Playtest (heuristic, 300 runs per class)

| Class | Boss reached | Clear rate | Level at boss (mode) | 1-dmg hits |
|:---|---:|---:|---:|---:|
| Warrior | 76% | 37% | 5 | 1.0% |
| Martial Artist | 68% | 44% | 5 | 1.3% |
| Priest | 79% | 59% | 5 | 1.2% |
| Mage | 82% | 62% | 5 | 1.1% |

The Mage sits 2 points over the 60% ceiling, which is within run-to-run noise. Its starting INT was
trimmed from 17 to 16.

### Manual playtest notes
- **Warrior (seed 515).** A CON +3 charm raised Max HP 130 → 148 and current HP by the same amount. One
  fight gave two level-ups, each fully healing (154/154, then 160/160). Levels on path labels read well
  ("Mire Toad (Lv 4)" on floor 3).
  - Observation: at low levels even an average roll counts as "big" relative to the floor, so a
    Warrior's level-2 roll of 3 points landed on CON, INT and CHA. This is the specified behaviour.
    Raise `level_up_points.floor` or reduce flattening if early levels should stay more on-class.
- **Mage (seed 616): found a hole.** EXP only came from fights while enemy levels rise with the floor, so
  a route through a rest and an event reached floor 4 at level 1 and met a level-5 elite. → An `exp`
  effect for events (floor-scaled) is now used by six events.
- **Priest vs the Warden (level 5, isolated).** A close fight (won with 6 HP left). Rolls varied from 4
  to 11 points; big rolls spread into off-class stats as designed.
- The character sheet now explains Max HP ("CON 16 gives 134, +15 bonus").

---

## Pass 2: The Lantern Road (2026-10-10)

**Branch:** `feat/content-pass` · **Plan:** content improvement plan (holes and bugs, dull areas, new
features).

### What changed
- **Setting.** An original setting replaces the Octopath name bank ([docs/world.md](../world.md)).
- **Classes.** Cut from 8 to 4 classic roles: Warrior, Martial Artist, Priest, Mage. Each has a combo
  kit (Sunder → Heavy Blow, Mark → Finishing Strike) and per-level growth.
- **Enemies.**
  - 15 normal and special enemies in early/mid/late floor bands, each with a gimmick and an intro line.
  - 3 elites and 3 preconstructed ordeals.
  - 2 phased bosses with telegraphed attacks.
- **Events and progression.** 13 occurrences (requirements, chance outcomes, event fights, class-only
  choices); 9 shop items; 16 class-aware perks.
- **Features.** Waystation shop, a camp between floors, save/load, name prompt, run summary.

### Playtest (heuristic policy, 300 runs per class, `python3 tools/playtest.py`)

| Class | Avg floor | Boss reached | Clear rate | Level at boss (mode) | Skill share | 1-dmg hits |
|:---|---:|---:|---:|---:|---:|---:|
| Warrior | 9.7 | 88% | 48% | 4 | 83% | 1.0% |
| Martial Artist | 9.3 | 81% | 59% | 4 | 83% | 1.5% |
| Priest | 9.3 | 76% | 59% | 4 | 99% | 1.5% |
| Mage | 9.5 | 81% | 56% | 4 | 90% | 1.4% |

All Phase 4 targets are met:
- boss reached ≥ 60%;
- clear rate 25–60%;
- level 4–5 at the boss;
- skill share ≥ 35%;
- fewer than 3% 1-damage hits;
- average floor ≥ 6.

The Attack-only policy clears **0%** for every class, so the kits matter. Before this pass, the seed
content's 8 classes cleared 0–13%, reached the boss at level 1–2, and barely used skills.

### Manual playtest notes

The four runs were played turn by turn at the console. The aggregate tool missed most of these
findings; all are fixed unless marked otherwise.

**Run 1 (Priest, seed 101): cleared the Mother of Moths at 17 HP. Saved mid-run and continued.**
- An event whose only usable choice was "decline" wasted a floor, and was offered again two floors
  later. → Occurrences need ≥ 2 usable choices to be offered.
- "You restore 0 STAMINA, 0 MANA" and "recovers 0 HP" messages. → Zero amounts are not narrated.
- REGEN "afflicted" the Priest. → Buffs read "gains".
- Raw keys `MAX_HEALTH` and `stout_heart` appeared in text. → Readable stat and perk names.
- A "GAME OVER" banner appeared after Save and quit. → A save-and-quit ending message.
- No skill descriptions in combat menus. → Added.
- CHA was a dead stat. → It now discounts shop prices; added a Silver Tongue perk.
- The same enemy was offered on three floors running. → Last floor's (and this floor's) enemies are
  avoided.
- Gold stolen by thieves was simply lost. → Defeating the thief returns it.

**Run 2 (Warrior, seed 202): died on floor 4. Found the worst bug of the pass.**
- **Stacked speed debuffs locked the player out of the fight.** Two Hollows stacked −25 Speed per hit
  until the Warrior got 1 turn per ~25 enemy turns. → Repeat modifiers from the same action refresh
  instead of stacking (unless tagged `stacks`), and turn speed has a 50% floor.
- The sparring "big man" was a pickpocketing Road Bandit. → A dedicated Pit Brawler.
- Fights started from events had no intro text. → Intros print for every fight.
- DEX/INT/WIS perks were offered to classes that don't use them. → Perks are class-filtered.
- The camp menu didn't show HP, so heals got wasted. → HP and gold in the camp prompt.

**Run 3 (Mage, seed 303): died to two Hollows on the first attempt; cleared on the replay.**
- Weaknesses were invisible, so the player can't know Hollows burn. → The first hit on a weakness or
  resistance announces it.
- The intro printed inside the combat header and was duplicated for identical enemies; two enemies
  were both called "Hollow". → Intros print once, before the banner; duplicates become Hollow A / B.
- "You lose 18 HP" printed before the text explaining why. → Flavour first (except after event
  fights).
- Mend (a known heal) couldn't be cast at camp. → Camp "Use a skill" for skills marked
  `usable_outside_combat`.
- Learning a technique shifted the Mage's Cast menu number. → The class's main category is listed
  first.
- A shop had no healing items; Antivenom was usable at camp, where it does nothing. → Waybread is
  always stocked; Antivenom is combat-only.
- A fire-weak Mage melted the Mother of Moths in 4 turns; three perk prompts followed the final boss.
  → Weakness reduced to −25%; no perk prompts after the final fight; a "THE END" banner.

**Run 4 (Martial Artist, seed 404): bad inputs on purpose.**
- Invalid numbers, letters and an empty name are all handled.
- Fleeing works; locked purchases can't be selected; the Mark → Finisher combo works.
- The same battle was offered twice on one floor. → No identical regular battles on a floor.

**Boss review (Warrior vs the Ashgate Warden):** lost with the Warden on 1 HP. A good fight.
- The delayed Lantern-Eater damage printed inside the player's turn, as if self-inflicted. → Delayed
  effects are tagged (`[Lantern-Eater] …`).
- "Brace yourself!" was wrong, because Defend doesn't reduce DARK. → The telegraph now says "heal up
  or finish it now".

### Open items
- The weakness hint repeats once per enemy instance, not once per enemy type per run.
- Event prices (peddler, scribe) ignore the CHA discount; only shops apply it.
- A rest stop can still be offered at full HP (only floor 1 is excluded).
- Some event stat rewards (e.g. the hermit's +3 INT) are off-class for some players.
- Enemy-only actions still live in the player action files (friction A7 from Pass 1).

---

## Pass 1: Octopath-seeded prototype


**Date:** 2026-10-10 · **Branch:** `feat/octopath-prototype-content`

### Goal

Populate the engine with a first-pass game inspired by *Octopath Traveler* (2018). Then find where the
engine and data formats are clunky by **authoring content without changing the engine**.

Content was written only as JSON. Anything the data could not express is logged here, not worked
around in code.

### What was built

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

#### How Octopath's systems were mapped

- **Weaknesses** map to negative resistances (`sword_resistance: -50` → 1.5× damage). This works well.
- **Weapon types** (SWORD, SPEAR, DAGGER, AXE, BOW, STAFF) became damage types, used alongside the
  elements (FIRE, ICE, LIGHTNING, WIND, LIGHT, DARK).
- **Boss telegraphs** (Gathering Inferno) use `SET` plus `DELAY NONBLOCKING`, the same pattern as the
  spec's Defensive Charge example.
- **Drain** (HP Thief, Blood Drain) uses `HEAL SELF PREVIOUS_DAMAGE_DEALT/2`. This works well.

### Playtest results

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

### Findings

Severity: **🔴 blocks a core Octopath mechanic** · **🟠 forces a clunky workaround** · **🟡 polish**.

#### A. Engine expressiveness: what the data could not say

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

#### B. Occurrences and progression

| # | Sev | Finding | Evidence | Suggested direction |
|:---|:---|:---|:---|:---|
| B1 | 🔴 | **Purchases have no gold check. This is an exploit.** Gold clamps at 0 but the item is still granted, and the message reads "You gain 0 gold." | Scholar with 0 gold buys a Fire Soulstone at the Rippletide stall and receives it. | Choice-level `requires` (`{"gold": 40}`, stat thresholds, class); unmet choices are hidden or disabled. |
| B2 | 🟠 | **No chance-based outcomes.** Octopath path actions (Steal, Allure, Inquire) succeed on a % roll that depends on level and class; here every choice is deterministic. | "Pick his pocket" always works. | `{"chance": 0.6, "success": [...], "failure": [...]}` on a choice. |
| B3 | 🟠 | **Occurrences can't start a fight.** Provoke and Challenge should trigger combat. | "Challenge him" just prints flavour text. | A `combat` effect type that runs `Combat` with listed enemies. |
| B4 | 🟠 | **Levelling is weak and slow.** There's no stat growth per level, only one perk, and players reach the boss at level 1–2. | Level-at-boss distribution above. | Per-class growth tables applied on level-up, and/or a faster EXP curve. |

#### C. Combat UX and readability

| # | Sev | Finding | Evidence | Suggested direction |
|:---|:---|:---|:---|:---|
| C1 | 🟠 | **Menu offers empty categories.** A Warrior can pick Cast ("You don't know any spells") and a Scholar can pick Technique. Each is a dead end. The playtest harness looped forever on this; `tools/playtest.py` now caps choices per run. | Found while building the heuristic player. | Hide or disable categories with no usable entries. |
| C2 | 🟠 | **Status ticks aren't attributed.** A POISON tick prints right after the enemy's action, so it reads as part of that attack. | Blotted Viper fight log. | Prefix hook narration (`[Poison] Hero takes 11 damage`). |
| C3 | 🟠 | **Hidden state.** `SET` narrates nothing, so a boss's "Gathering Inferno" charge is invisible until it lands. Buff/debuff *expiry* is silent (only statuses announce wearing off). Turn order and speed changes are never shown. Weaknesses are invisible, so there's no Analyze. | Guardian of the First Flame. | Optional `"message"` field on actions; narrate modifier expiry; a turn-order preview line; an Analyze-style reveal. |
| C4 | 🟡 | **Flat Defense subtraction makes weak hits feel bad.** In Cleric runs, 12% of all hits (both sides) dealt exactly 1 damage. The Cleric's staff attack (6.4) against Defense 3–5 is the main source. | 1,447 of 12,393 hits (heuristic, 300 runs). | Percentage mitigation (e.g. `dmg × 100/(100+def×k)`) instead of subtraction. |

#### D. Balance (data only, no engine change needed)

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

### Recommended order

1. **B1** (exploit) and **C1** (dead-end menu): small, high value.
2. **A4** (damage category vs type) and **C2**/**C3** narration: cheap; they make the weakness game
   readable.
3. **A1** (Break) with **A5** (action-blocking statuses): together they unlock Octopath's core loop on
   the existing hook system.
4. **A2** (party) and **A3** (Boost): the large structural decisions. Decide whether the game is
   party-based before investing more in balance.
5. Balance pass (section D) once the above settle.
