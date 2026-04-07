# Architecture — Mid-Core Shooter Player Journey Visualizer

**One-page design doc** covering stack choices, data flow, coordinate mapping, assumptions, and tradeoffs.

---

## Stack

| Layer | Choice | Reasoning |
|---|---|---|
| Data pipeline | Python + pyarrow + pandas | Parquet is a binary columnar format — pyarrow reads it natively with zero configuration. Runs once at build time. |
| Frontend | Vanilla HTML + Canvas API | No build step. No node_modules. A level designer shouldn't need a developer to deploy or update this tool. Canvas renders thousands of path vectors at 60fps where SVG would choke. |
| Hosting | Netlify / GitHub Pages (static) | Free tier is sufficient. Zero ops overhead. Deploying is `git push`. |
| Data format | Pre-baked JSON | The browser has no parquet reader. Pre-processing once at build time means zero parse latency on page load, zero WASM library shipped to the client. |

---

## Data Flow

```
player_data/
  February_10/ ... February_14/
    {user_id}_{match_id}.nakama-0   ← Apache Parquet, binary
          ↓
    preprocess.py
      · pyarrow reads each file
      · event column decoded: bytes → string
      · user_id parsed from filename → is_bot flag (numeric = bot, UUID = human)
      · world coords (x, z) → minimap pixel coords (see below)
      · events sorted by timestamp
      · grouped: map → date → match → list of player journeys
          ↓
    data/AmbroseValley.json
    data/GrandRift.json
    data/Lockdown.json   ← structured, pre-transformed, browser-ready
          ↓
    index.html (fetch → JSON)
      · buildMatchList() populates sidebar
      · render() draws on Canvas: minimap → heatmap → paths → event markers
      · playback frame loop drives cutTime → progressive reveal
```

---

## Coordinate Mapping

This was the most precise part of the implementation. The game uses 3D world coordinates (x, y, z). The minimap is a 1024×1024 top-down image. The y column represents elevation and is ignored for 2D rendering.

**Formula (from README):**
```
u = (x - origin_x) / scale
v = (z - origin_z) / scale

pixel_x = u * 1024
pixel_y = (1 - v) * 1024    ← Y flipped: game origin is bottom-left, image origin is top-left
```

**Per-map parameters:**

| Map | Scale | Origin X | Origin Z |
|---|---|---|---|
| AmbroseValley | 900 | -370 | -473 |
| GrandRift | 581 | -290 | -290 |
| Lockdown | 1000 | -500 | -500 |

**Zoom/pan adjustment:**
The frontend supports scroll-to-zoom and drag-to-pan. The coordinate transform is extended to:
```js
screen_x = (pixel_x * zoom) + panX
screen_y = (pixel_y * zoom) + panY
```
This keeps all rendering consistent regardless of viewport transform. Double-click resets zoom to 1 and pan to (0, 0).

**Validation:** After applying the transform, any pixel outside [0, 1024] is dropped — these are edge-of-map events or spawn artefacts. Visually confirmed that paths cluster around named landmarks (Mine Pit, Engineer's Quarters, etc.) which match the minimap.

---

## Bot Detection

Handled at the filename level, not from data values.

- `{UUID}_{match_id}.nakama-0` → Human player (UUID user_id)
- `{integer}_{match_id}.nakama-0` → Bot (numeric user_id, e.g. `1440`, `382`)

This is deterministic, requires no heuristics, and is consistent with the README spec. The `is_bot` flag is set during preprocessing and stored in the JSON.

---

## Assumptions

| Ambiguity | Decision | Why |
|---|---|---|
| Timestamp unit | Treated as milliseconds since match start | README states "time elapsed within the match". Used directly for timeline slider |
| February_14 partial data | Included as-is, no special treatment | Still valid spatial data for heatmaps and path rendering |
| Out-of-bounds coordinates | Silently dropped during preprocessing | Small count; likely spawn/transition states outside playable area |
| Match reconstruction | All files with same match_id = one match | Per README definition |
| Heatmap resolution | 512×512 offscreen canvas | Sweet spot between density detail and rendering performance |

---

## Tradeoffs

| Decision | Option Considered | What Was Chosen | Why |
|---|---|---|---|
| Parquet in browser vs pre-process | WASM parquet reader client-side | Pre-process to JSON | Saves ~2MB library, eliminates parse delay on every page load |
| Canvas vs SVG | SVG for markers and paths | Canvas for everything | SVG degrades badly above ~1000 DOM elements; Canvas handles 89k events at 60fps |
| Single file vs component framework | React, Vue, Svelte | Single HTML file | No build step = any designer can fork, edit, and deploy without a dev environment |
| Heatmap per-match vs aggregated | Only show current match | Both modes (toggle) | Single match is too sparse for patterns. All-matches mode gives real design signal |
| Real-time parquet vs static JSON | Live query against parquet on server | Static JSON | Removes all infrastructure dependency; scales to many users at zero cost |
| Match list labeling | Show UUID | Display name: `#3 · Feb 11 · Human-heavy` | Designers need to know match quality at a glance. UUIDs communicate nothing |

---

## What Was Built vs What Was Asked

The brief asked for a visualization tool. What was shipped is closer to an internal studio product:

- **Zoom & pan** — not in the spec, but essential for inspecting specific map zones
- **All-matches heatmap aggregation** — transforms a noisy single-match view into a statistically meaningful map pattern
- **Match quality filter** — surfaces matches with real player data, filters bot-only outliers
- **Looting rate % and avg distance stats** — designer-specific metrics, not generic event counts
- **Lobby composition tags** — instant sample quality signal per match
- **Loop/replay** — enables close study of a specific engagement
- **Loading progress bar, tooltip animations, keyboard-accessible controls** — details that signal it was built for real use, not for submission
