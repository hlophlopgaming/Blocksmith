---
name: 3d-level-design
description: >-
  Design and generate 3D levels: beats and pacing, zone graphs, layouts, metrics,
  blockouts without gaps or overlaps, encounters, cover, wayfinding, and gates.
  Use for any task to create, generate, plan, or evaluate a level, map, arena,
  dungeon, or room, even when the request does not explicitly mention level design.
---

# 3D level design: how to generate levels

This method is based on The Level Design Book (book.leveldesignbook.com, CC BY-NC-SA 4.0), paraphrased here. The book primarily covers 3D action games; for other genres, use the sections on goals, pacing, gates, and wayfinding, and skip the combat sections.

## Core principles

- **A level is a place, not a picture or a document.** Players control their own camera and route. Design a space that works from different viewpoints and with different player behaviors, rather than a single attractive shot.
- **A plan proves nothing.** A drawing or document cannot be played. Only a playable blockout and playtesting will show whether the level works. As an agent, you cannot play it yourself, so (a) deliver something a person can run as early as possible, (b) mentally walk through the level, and (c) formulate playtest hypotheses instead of claiming that the level is good.
- **Keep the level cheap to change.** Start with gray primitives, then add scripts and lighting, and leave art until last. Premature detail makes revisions expensive.
- **Derive decisions from the intended experience**, rather than from rules for a supposedly good level. An inefficient route, dead end, sharp turn, or lack of cover can all be useful tools when they serve the goal.
- **Design for the specific game, not the genre.** Movement speed, jumping, weapons, and enemy roster determine the shape of the space.
- **Do not rely on shape and color psychology or leading lines** to direct players: the book considers them unreliable. Use contrast, landmarks, vantage points, metrics, and in-game testing instead.

## Step 0. What to establish before starting

Find the information in the project (GDD, player controller code, existing scenes), or ask. If no source is available, make a reasonable assumption and state it explicitly in the output.

1. **Mode**: single-player/PvE or PvP. Almost everything depends on this distinction; see the multiplayer section.
2. **Mechanics**: primary mechanics that recur throughout play, and secondary mechanics. What does the player do most often?
3. **Physical player metrics**: take these from the engine or code rather than inventing them: collider width and height, camera height, walking and running speed, jump height and distance, maximum step height and slope angle, and fall damage.
4. **Enemy roster and weapons**, if there is combat: roles, range, and speed.
5. **The level's place in the game**: what the player already knows, what came before, and what follows.
6. **Scope**: playthrough duration and number of zones. Beginners almost always plan too much: imagine the smallest version, then cut it in half again.
7. **Output format**: document, data (JSON/graph), engine scene, .map file, or tile grid.

If a mechanic is new and untested, first propose a test playground, a large box with different floors, heights, and obstacles, rather than a finished level.

## Pipeline

Follow the steps in order; returning to an earlier step is normal. For a small room, steps 1–4 may take only a few lines each, but keep them: goals and beats provide the basis for later decisions.

### 1. Experience goals and pillars

Write 1–3 goals in the form, “In this level, the player should [learn / feel / do] …”. “Make it fun” is not a goal that helps choose between alternatives. Example: “Feel cornered at the beginning and in control at the end” → start in a cramped space and finish on high ground with a clear view.
Each goal should support at least one project pillar, the game's 2–3 main themes, if these are defined.

### 2. Beats and pacing

A **beat** is a small, self-contained piece of the level: an area, event, fight, puzzle, or scene. Create a beat sheet and give each beat a type and an intensity from 0–10. Useful types include exploration, combat, puzzle, and scene/dialogue; define others if the game needs them. Intensity means tension and stakes, not difficulty.

The pacing plan should answer five questions: what the player can do (scope), what matters most (hierarchy), why one thing precedes another (causality), what the player learns and when (information), and where tension and rest occur (intensity).

Pacing rules:

- **Start quietly**: use a low-intensity first beat to let players settle in, look around, and absorb the mood.
- **Alternate peaks and valleys.** Prolonged tension is tiring; rest after combat feels rewarding. Avoid more than two or three intense beats in a row without a break; a boss fight longer than ~10 minutes becomes routine.
- **Teach → test → twist**: introduce a technique safely, let the player repeat it with a hint, then change the conditions and remove the hint. Leave some space between the test and the twist.
- **Rhythm**: a recurring motif, accent, pause, variation, and subversion of expectations. Subversion works only after the expectation has been established.
- **Set piece**: a particularly spectacular and expensive beat. Plan at most one per level, and only one that can realistically be finished.
- **The ending need not be the hardest part**: the resolution may be easier than the climax and should follow from what came before.

### 3. Parti and typology

The **parti** is the level's main structural idea, expressed in one sentence and one sketch: for example, “a tower you circle in a spiral while always seeing its summit.” Sketch 5–10 one-line alternatives, choose one, and explain the choice through the experience goal.

Build the structure from familiar patterns:

| Pattern | What it provides | What to watch |
|---|---|---|
| Corridor | Full control over sequence and timing | Speed up: descent, one-way drop, bright light. Slow down: alcoves, side rooms, pools of light |
| Hairpin loop (dead end with a return) | Light exploration and brief disorientation | Hide the exit if you want the dead end to be explored |
| Bowl with central cover | Circular movement in fast combat | A drop or height change establishes direction |
| Arena / point of interest | Open space, multiple approaches, central cover | In single-player, lock it down to prevent early departure or enemies being lured into a doorway |
| Hub and spokes | Clear structure; returning to the hub offers rest | The hub should change on each return, or it becomes mere backtracking |
| Loopback | A sense of nonlinearity with linear control | An overly convenient loopback feels artificial |
| 1–3 lanes | Predictability and coordination in PvP | See the multiplayer section |

Typology is a vocabulary, not a law: depart from it when the goal calls for it.

### 4. Zone graph (bubble diagram)

Turn beats into a graph: nodes are zones, sized by importance, and edges are connections. Create at least 2–3 alternatives and compare them. For each node, specify its name, beat(s), purpose, approximate size, and floor. For each edge, specify the type (passage, door, drop, stairs, elevator), direction (two-way or one-way), and gate.

The **critical path** is the shortest route from start to exit through the required beats. Mark the start and exit, and number the beats. Only some players will see content outside the critical path, making it the first candidate to cut when time is short. Avoid reducing the level to a bare checklist: in games where a believable place matters, first invent a plausible place, then route the path through it.

**Circulation.** Main passages are wider and more noticeable; secondary passages are narrower. Context matters more than size: a large door resembling a garage door reads as closed. For narrative levels, ask how the world's inhabitants would move through the space, and compare with real layouts of similar places.

**Use verticality sparingly.** Limit each zone to three floor planes (low, middle, high); merge minor height changes into one floor. Going down is easier than going up: a one-way drop commits progress and prevents retreat from combat. Reserve space for stairs, a ramp, or an elevator before adding an ascent. Every height change should have a reason.

**Gates** are anything that stops movement:

- Hard: progression requires a condition, such as a key, killing all enemies, or a timer. Use for mandatory content.
- Soft: bypassing is possible but costly, such as an exposed exit or a slow-opening door.
- Hidden exit: a reward for exploration.
- Reverse gate (one-way entry): prevents backtracking.
- Shortcut: a hard gate opened from the far side that shortens the return route.

Lock and key: show the lock before providing the key. Place the key where the lock is visible, or remind the player of it. If multiple keys are required, the lock itself should communicate their number.

### 5. Metrics

There are two kinds: **player metrics**, which are facts from the engine, and **architectural metrics**, which you choose to serve the experience goal. Build at player scale rather than real-world scale: something that feels large in a game should be noticeably smaller than its real counterpart. Internal consistency matters most.

Starting dimensions from the book; adapt them to your game:

| | Engines using meters (Unity; Godot by analogy) | Unreal (cm) | Quake / Source (units) |
|---|---|---|---|
| Player collider W×H | 1.0 × 1.8–2.0 | 60 × 176 | 32 × 72 |
| Camera height | 1.5–1.7 | 152 | 64 |
| Interior wall thickness × height | 0.1 × 3.0 | 20 × 300 | 16 × 128 |
| Minimum corridor width | 2.0 | 150 | 64 |
| Door W×H | 1.25 × 2.5 | 110 × 220 | 56 × 112 |
| Step rise × tread | 0.1 × 0.15 | 15 × 25 | 8 × 12 |
| Grid spacing | 1 or 2 | 50/100 or 64/128 | 32 or 64 |

Rules:

- Derive grid spacing from player width; place everything on the grid.
- Corridors and openings should be at least two player widths wide, which is still tight. Doors are narrower than corridors.
- Blockout walls should be 150–200% of player height.
- Stairs: a 30–35° slope, with a landing every 12–16 steps. Use a ramp instead of individual steps in the blockout.
- Avoid thin floors and walls: they cause collision failures and look like cardboard.
- Corners of 90° or sharper block sightlines; rounded or beveled corners open sightlines and accelerate movement.
- Cover, using Uncharted 4 as a reference: high cover starts at 1.75 m, low cover is 1.0–1.25 m, and anything up to 0.5 m does not count as cover. Avoid intermediate heights if the game has a cover system.
- Define close, medium, and long combat ranges from your game's weapons, and define the size of a large fight; derive arena dimensions from these. Example proportions from TF2: 256 / 1024 / 2048 units; a drop without damage is 256.
- Unusual metrics, such as overly steep stairs or a low ceiling, create tension. Use them intentionally against a backdrop of familiar dimensions.
- Fix camera height and FOV early: they affect the perception of size and speed.

### 6. Layout and blockout

For the top-down layout, start with large features and add detail gradually; draw only what is needed to imagine the player's experience. Keep it boxy: about 90% of corners should be right angles and aligned to the grid. Overlay the critical path, start and exit, zone names, landmarks, key objects, and enemies. Show multistory spaces with a separate section or one plan per floor.

Blockout:

1. Ground plane, player-scale reference figure, and walls. Give walls and floors different colors, and use a grid texture with a consistent scale (world-aligned / triplanar).
2. An opening is a break in the wall; a window is the same break with a waist-high wall beneath it.
3. Assemble primitives or a modular kit using engine tools so collision and walking work immediately.
4. Add a player start immediately, so a person can walk through with actual gravity and movement speed instead of flying the editor camera.

**Massing**: every volume has a function; important places are larger and more distinctive than their neighbors. Contrast with the surroundings establishes hierarchy through height, density, rotation relative to the grid, and shape. Simple forms in clear groups read better; overly fragmented massing becomes noise.

### 6a. Geometry joins: no gaps or overlaps

When generating a level through code, an agent tends to fail in two ways: leaving gaps and holes between pieces (visible background, falling through, or getting stuck), or pushing pieces into one another so surfaces overlap (coplanar flickering, doubled walls, props sunk into floors). Use precise joins: neighboring pieces meet face to face, and no point in space belongs to two pieces at once.

**Calculate positions rather than eyeballing them:**

- All dimensions and positions are multiples of the grid spacing. Store coordinates as integer grid cells and multiply by spacing only when creating the object to avoid accumulating fractional errors.
- Remember that a box position is usually its center: edge = center ± half the size. Most gaps and overlaps come from forgetting half the size or the wall thickness.

**Define who owns each join once, then apply that rule everywhere:**

- The floor is a slab covering the room's full outline, including the space beneath walls. Walls stand on the floor (wall bottom = floor top), rather than inside it. The ceiling rests on the walls.
- At corners, walls along one axis run the full length; walls along the other axis fit between them and are shorter by two wall thicknesses. This closes the corner without intersections.
- Two neighboring rooms share one wall, rather than two adjacent or intersecting walls. Generate walls from edges in the room graph instead of generating them separately for each room.
- Make wall openings by splitting the wall into segments (left, right, and lintel), rather than placing a door over a solid wall.
- Props, cover, stairs, and ramps stand on the floor: object bottom = floor top; the top of a ramp is flush with the upper landing edge.

**Prevent:**

- Two surfaces in the same plane, which causes flickering; wall decoration should either be inset or clearly offset.
- Duplicates: the same piece created twice in the same location, a common error in room loops. Track a set of keys for pieces already created.
- Deliberate gaps or overlaps used as a margin to hide a seam.

**Exception.** If precise joining is impossible, such as with pieces rotated off the grid or organic shapes, deliberately embed one piece deeply into its neighbor so that no pair of faces is coplanar, and hide the seam with a prop. Make this an explicit decision and record it in the output.

**Check with a script, not by eye**, using a tolerance of about 0.001 units:

- Overlaps: compute bounding-box intersections for every pair of pieces. Face contact is allowed; overlap greater than the tolerance along all three axes is an error.
- Gaps: for pieces intended to join, the distance between facing surfaces must be zero within the tolerance.
- Sealing: flood fill through free cells from the start must stay inside the level's outer boundaries and reach all zones.
- Duplicates: no two pieces may have the same position and dimensions.

### 7. Encounters and cover, if there is combat

An **encounter** is a sequence of systemic challenges that allows different tactics. There should not be only one correct solution.

For each encounter, describe the combat narrative:

- Before: are enemies already fighting, unaware of the player, or approaching? Does the player choose when to enter? Can the player see the arena and enemy composition beforehand?
- During: how many waves and phases are there, what changes the course of the fight, and which routes should stand out?
- After: how does the player know the fight has ended?

**The doorway problem.** If combat starts on entry, the player fights from the doorway while the arena goes unused. Provide a staging area in one of these ways:

1. The player sets an ambush: enemies are visible from the entrance and unaware; reinforcements emerge around a corner after combat starts.
2. The player is ambushed: the arena is empty, and enemies appear once the player reaches its center, perhaps drawn by bait. This works once; avoid making it lethal.
3. A vantage point with a one-way entrance: the player sees the arena but cannot attack from there; a drop or closing door commits entry. This is the fairest option and works well for bosses. If players ignore the vantage point, place resources there or route the approach through a turn.

**Enemy palette** for one encounter:

| Types | Purpose |
|---|---|
| 1 | Teaching or rest |
| 2 | A regular fight: an interesting relationship emerges between the types |
| 3 | Difficult: three relationships at once are hard to read |
| 4 | Readable only as two opposing factions |
| 5+ | A chaotic brawl: vivid, but only briefly |

Roster roles include a basic melee enemy, a medium-range squad, a leader who buffs allies, a slow and durable tank, a swarm of small fast enemies, and a sniper. Check the spread of speed, health, range, and damage. Ranged enemies make height and cover important; melee-only enemies do not. A combination should disrupt the tactic that works against each type alone. Enemy silhouettes should be readable from 10+ meters away.

**Player personas**: name 2–3 play styles for the project, and check that each has a viable tactic in the arena.

**Cover.** More cover means slower combat. Less is usually better:

- Prefer low cover to high cover so the player can keep seeing the fight.
- In single-player, leave enemies partly exposed; an invisible enemy undermines the value of a position.
- Many wide, tall cover pieces turn an arena into a maze.
- Directional cover, such as a wall, leaves a flank and suits a front line. Freestanding cover, such as a pillar or crate, enables circular duels and suits a last stand.
- Avoid identical cover crates at regular intervals: integrate cover into the architecture and use slopes.
- Tutorials and bosses often work better in an open, flat arena.
- Stealth and shooters need opposite layouts: in stealth, enemies stand in the open and control the middle, while the safe route runs along the side with exposed gaps. In a shooter, enemies are behind cover, the middle is no-man's-land, and the side route rewards observant players.

Single-player is intentionally unbalanced in the player's favor: the AI's job is to lose in an interesting way.

### 8. Navigation (wayfinding)

Rather than leading players, provide information. Decide early whether the experience is guided or whether finding the route is part of play, in which case use fewer cues.

Players build mental maps from paths, edges, districts, nodes, and landmarks. Give each zone a distinct identity and place a visible landmark at junctions. A landmark counts only when it helps orientation; attractive decoration alone does not.

Tools ranked by reliability; the percentages are approximate:

- **Subtle (up to ~20% of players notice)**: world logic, sound, unusual details, and room typology. Use for secrets and polish.
- **Moderate (35–60%)**: sightlines and tall landmarks, light and color, signs, tracks and ground paths, and repetition of familiar patterns. Use for the critical path and optional routes.
- **Strong (70–93%)**: scripted events, trails of resources, cutscenes, world-space markers, and attacking enemies.
- **Direct (95%+)**: a chasm, wall, objective marker, or minimap.

Start with the subtlest tools that might work, then strengthen them based on playtests. Provide a vantage point before a complex arena. Remember three observations: players rarely look up without a reason, look where they are going, and notice contrast in color, shape, light, and movement.

### 9. Scripting: objectives, triggers, doors

- First describe the logic as a flowchart: objectives → conditions → events. Then implement the simplest version.
- In single-player, triggers are unobtrusive; in multiplayer, they are visible and readable.
- Start with buttons and pickups. **A door is the most complicated simple object**: first ask whether it is needed at all. Sliding doors are simpler than hinged doors. A hinged door opens away from the player. Player convenience matters more than realism. During exploration, leave opened doors open so players can see where they have been; during combat, close doors behind the player.
- Door states: open, closed, opening, closing, and locked. Handle someone standing in the doorway.
- Mark cover nodes and forbidden areas for AI.
- A simple hack can work for a short project; a long project calls for a systemic solution.

### 10. Lighting, after blockout gameplay has settled

Work in passes: 1) general lighting (key, fill, sky); 2) the critical path, lighting entrances and exits from the approach side, with main exits more noticeable than secondary ones; 3) gameplay, hinting at combat and highlighting puzzle elements and exploration opportunities; 4) detail and mood, without overdoing it.
Techniques include a single light as an attractor, a pair of matching lights framing an entrance, and a lit wall as a guide. Give every light a plausible source, such as a lamp, window, or campfire. Keep base textures within 50–100% brightness so shadows do not become too dark after baking.

### 11. Art

Only begin once the layout has settled. Start with large forms and the palette; leave small details until last. Every detail affects readability: group details into clusters, avoid fully saturated colors, associate colors with functions, and make materials distinguishable at a distance.

## Multiplayer (PvP)

- Aim for fairness as perceived by players, rather than mathematically perfect balance; use roughly a 50% win rate for each side as a reference.
- Use **1–3 lanes** with a clear hierarchy; more become a maze. Distinguish lanes by length, landmarks, or objectives. Connect lanes for flanking and rotations.
- Use **3–4 chokepoints**, roughly one per lane; no single position should control all of them.
- Evaluate each area along three axes: utility (why go there), cost (how hard it is to take and hold, and what this exposes), and information (whether players know about it). An area that is always useful, cheap, and visible becomes a dominant strategy. Every strong position should have a situational weakness; a position without weaknesses is a camping spot.
- Check each position: can someone sneak up on it? Do all enemy sightlines fit within one field of view? Is there a height advantage?
- Symmetry, mirrored or rotated by 180°, is the simplest route to balance; distinguish the sides through art. Asymmetry requires far more iteration.
- Keep travel time from spawn to the objective short; a practical example is 8–12 seconds. If the route feels long, it is long.
- Use less cover in PvP than in PvE, and even less when players have smoke and shields.
- Limit verticality, especially for gamepads: use wide spaces, gentle slopes, and clear floor planes.
- Vary sightline lengths; provide multiple views of each landmark from different positions.

## Tuning values

On the first pass, change values by a factor of two, doubling or halving them: small changes are hard to notice. Find the bounds first, then narrow the range. If an element is weak and the fix is unclear, strengthen it: nobody uses a weak element, so it produces no data. Players are usually right about symptoms and wrong about causes.

## Self-check before delivery

If the level exists as data, such as a graph, grid, or scene, write and run a validation script rather than judging it by eye.

**Mechanical checks:**

- [ ] The exit and every required zone are reachable from the start.
- [ ] There are no softlocks: every key is reachable before its lock; one-way drops and closing doors do not cut off mandatory content.
- [ ] Each lock is encountered along the route before its key.
- [ ] Every opening and corridor meets the minimum width; all jumps and steps stay within player metrics.
- [ ] Geometry is on the grid; walls and floors are not thin; each zone has at most three floor planes.
- [ ] No overlaps: no pair of pieces intersects in volume; no coplanar overlapping faces; no duplicates.
- [ ] No gaps: intended joins meet face to face, and flood fill from the start stays within the level boundaries.
- [ ] Props, cover, and stairs stand on the floor, neither sunken nor floating.
- [ ] The intensity curve starts quietly and alternates peaks with valleys.

**Mental walkthrough**, experiencing the level as a player, beat by beat:

- [ ] At each point: what do I see, do I know where to go, and what tells me that?
- [ ] Does the desire line, where the player wants to go, match the actual route, or is the mismatch intentional?
- [ ] Every fight has a staging area beforehand and a clear ending.
- [ ] Every player persona has a viable tactic.
- [ ] Every beat serves the stated experience goal; unnecessary content has been cut.
- [ ] Walk through again as a speedrunner and as a lost beginner.

## Output format

Unless the user specifies another format, deliver:

```
# <Level name>
## Experience goals and assumptions
## Parti (one sentence) and selected typology
## Beats: number | zone | type | intensity 0–10 | what happens | why
## Zone graph: nodes, edges, gates, critical path
## Metrics: player (from the engine) and architecture (chosen)
## Layout: top-down plan per floor with a legend (ASCII or image)
## Encounters: staging area | palette | combat narrative | cover
## Wayfinding: landmarks and cues at every junction
## Scripts: gates, triggers, doors
## Geometry validation: script results (overlaps, gaps, duplicates)
## Playtest hypotheses
```

Then, if you have access to the project, build a playable blockout in the engine and explain how to run it.

**Playtest hypotheses** are required: provide 3–5 specific questions that only a human player can answer, such as “Do players find the exit from zone 3 in under a minute?” or “Do they use the vantage point before the arena?”, along with what to measure and the session duration. Recommend observing behavior silently: it matters more than opinions.

## Common agent mistakes

- Starting with geometry before recording experience goals and beats.
- Delivering an attractive description or image instead of a playable blockout.
- Copying real-world dimensions.
- Adding steps, platforms, and cover for interest without a reason.
- Starting combat in a doorway.
- Placing pieces approximately: leaving gaps between walls, pushing pieces into one another, or duplicating walls between neighboring rooms.
- Mixing four or five enemy types in a regular fight.
- Decorating before the layout has settled.
- Claiming that a level is balanced or interesting without playtesting.

## Source

The Level Design Book — https://book.leveldesignbook.com/ (CC BY-NC-SA 4.0). The book is unfinished, and some pages are placeholders. For details, consult Process → Pre-production, Combat, Layout, Blockout, Scripting, Lighting, and Environment Art. Index of all pages: https://book.leveldesignbook.com/llms.txt
