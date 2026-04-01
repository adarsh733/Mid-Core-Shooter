# Insights — LILA BLACK Player Data Analysis

Three findings from 5 days of production telemetry (Feb 10–14, 2026).
**796 matches · 89,104 events · 339 unique players · 3 maps**

---

## Insight 1: Grand Rift Is Effectively Absent from the Rotation

### What caught my eye
Switching the map tab to Grand Rift, the match list was noticeably short. The heatmap was sparse. Something felt structurally wrong.

### The numbers
| Map | Matches | Share |
|---|---|---|
| AmbroseValley | 566 | 71% |
| Lockdown | 171 | 21% |
| **GrandRift** | **59** | **7%** |

Grand Rift received **10× fewer matches than AmbroseValley** across the same 5-day window. It is not just less popular than the primary map — it is nearly absent. Lockdown, the smallest map in the game, still runs at 3× Grand Rift's match volume.

At 59 matches in 5 days (~12 per day), there is not enough data to draw reliable conclusions about player behavior. A single design change has no measurable feedback loop at this sample size.

### What a level designer should do
First, determine whether this is a **matchmaking weight problem** or a **player preference signal**. Check backend queue data: are players being assigned to Grand Rift and re-queuing? If yes, the map has a retention problem and needs investigation. If no, it is being systematically under-weighted in the rotation.

Until resolved, the tool's heatmaps and path analysis for Grand Rift are statistically unreliable — too few matches to distinguish pattern from noise.

**Metrics to watch:** Map assignment rate, re-queue rate after Grand Rift matches, average session length per map.

---

## Insight 2: 93% of Players Leave Without Picking Up a Single Item

### What caught my eye
Enabling the Loot layer in the visualization, the green diamond markers are nearly invisible across most matches on all three maps. Toggling it on and off produces almost no visible difference.

### The numbers
Out of 782 human player files across 5 days, only **55 (7%) contain any Loot event**. That means **93% of human players complete an entire match without picking up one item.**

This is not explained by short match duration. Players with zero loot events still show long movement paths — they are alive, traversing the map, and dying to combat or extracting without ever looting. The activity is happening. The looting is not.

### What a level designer should do
Use the tool to overlay the Loot markers with the Traffic heatmap. If loot markers appear predominantly in low-traffic zones, the loot spawn positions are misaligned with player routes — the fix is repositioning spawns into high-traffic corridors.

If loot markers and traffic overlap but the rate is still near zero, the issue is one of two things: players are dying to combat before they can loot, or the interaction cue for loot is not discoverable enough. These require different fixes (combat balance vs UI feedback) and the data alone cannot distinguish them — a follow-up playtest would clarify.

**Metrics to watch:** Loot interaction rate per player, time-to-first-loot, loot events per match normalized by match duration, loot spawn coverage heatmap vs traffic heatmap overlap.

---

## Insight 3: The Storm Is Not Driving Behavior

### What caught my eye
With the Storm Deaths layer enabled, the purple markers are nearly absent — isolated single events scattered across five days of data. In a mechanic designed to compress the playable zone, create urgency, and eliminate camping, I expected clusters.

### The numbers
`KilledByStorm` events appear in **9 player files out of 799 that have movement data** — a **1.1% storm death rate**. For context, `BotKill` events appear in 713 files. Players are dying to AI opponents at **79× the rate they die to the storm**.

Using the timeline playback, watch a match unfold. Most player paths end in the first half of the match timeline — well before the storm would become relevant at typical extraction-shooter timing. Players are dying to combat before the storm is a factor.

### What a level designer should do
The storm is a pacing mechanic. A 1.1% lethality rate means it is not fulfilling that role — players simply do not interact with it.

Two hypotheses and corresponding tests:
1. **Storm timing is too slow** — players consistently extract or die before the storm reaches combat zones. Fix: accelerate the storm's closure schedule by 20–30% in a test build and measure whether deaths shift later in the match timeline.
2. **Storm zone shrinks to areas players have already left** — the direction and destination of the storm contraction may not intersect with active combat zones. Fix: map the storm's final position against the traffic heatmap. If they don't overlap, the storm path needs redesigning.

**Metrics to watch:** Storm death rate, percentage of players alive when storm reaches 50% map coverage, median match duration vs storm closure timeline, extraction success rate before and after storm acceleration.
