# MetalGPT - Thought Experiment Notes

**Date:** 2026-03-29  
**Status:** Active thought experiment  
**Goal:** Build an AI-native casting design tool that replaces MAGMA software

---

## Core Insight

Don't recreate MAGMA's simulation-heavy approach. Instead:
- Strip away compute-intensive meshing/CFD
- Use AI + geometric analysis + engineering knowledge
- Enable fast, explainable design decisions
- Browser-based, self-contained

---

## Architecture

```
┌─────────────────────────────────────────┐
│           BROWSER APP                   │
├─────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    │
│  │  3D Viewer  │◄──►│  AI Chat    │    │
│  │  (Three.js) │    │  (Claude/   │    │
│  │             │    │   GPT-4)    │    │
│  │ - STEP file │    │             │    │
│  │ - Risers    │    │ - Natural   │    │
│  │ - Channels  │    │   language  │    │
│  │ - Risk map  │    │ - Sketches  │    │
│  └─────────────┘    └─────────────┘    │
├─────────────────────────────────────────┤
│         LOCAL AI ENGINE                 │
├─────────────────────────────────────────┤
│  ┌─────────────────────────────────┐    │
│  │      GEOMETRIC ANALYSIS         │    │
│  │  - Thickness map (fast)         │    │
│  │  - Volume/surface ratios        │    │
│  │  - Section transitions          │    │
│  │  - NO MESH - just B-rep math    │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │      KNOWLEDGE ENGINE           │    │
│  │  - Chvorinov rules              │    │
│  │  - Feeding distance tables      │    │
│  │  - Material property DB         │    │
│  │  - Design patterns              │    │
│  │  - Failure mode library         │    │
│  └─────────────────────────────────┘    │
│  ┌─────────────────────────────────┐    │
│  │      AI REASONING               │    │
│  │  Input: Geometry + Material     │    │
│  │  Output: Design plan + Risks    │    │
│  │  NO SIMULATION - just reasoning │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

---

## Workflow

```
User drops STEP file
    │
    ▼
AI: "Analyzing geometry... Found 3 thick sections"
    │
    ▼
[3D view with colored risk map]
🔴 Red: Thick sections (last to freeze)
🟡 Yellow: Transitions (stress risk)
🟢 Green: Thin sections (safe)
    │
    ▼
AI: "Steel bracket with thick bosses. Sand cast?"
    │
    ▼
User: "Yes, A356"
    │
    ▼
AI: "Here's my plan:
     1. Top riser on boss A (modulus 2.1)
     2. Side riser on rib B (modulus 1.8)
     3. Chill at corner C
     [shows 3D preview]
     Adjust or approve?"
    │
    ▼
User: "Move riser 2 to corner"
    │
    ▼
[cad modify --id riser_2 --position "80,60,40"]
    │
    ▼
AI: "Done. New feeding distance: 45mm ✓
     Yield: 68% → 64%
     [updated 3D view]"
    │
    ▼
User: "Export"
    │
    ▼
PDF with:
- 3D views
- Riser dimensions
- Gating sketch
- Design rationale
- Risk assessment
```

**Total time: 2 minutes**  
**No simulation ran.**

---

## Knowledge Base Structure

```
knowledge/
├── core/
│   ├── chvorinov_rules.md          # Solidification time
│   ├── feeding_distances.md        # By material & section
│   ├── riser_design.md             # Thumb rules
│   ├── gating_ratios.md            # Sprue:runner:gate
│   └── defect_modes.md             # Why things fail
│
├── materials/
│   ├── steels.md                   # All grades
│   ├── aluminum_alloys.md          # A356, A380, etc
│   ├── irons.md                    # Gray, ductile
│   └── superalloys.md              # IN718, etc
│
├── processes/
│   ├── sand_casting.md
│   ├── investment_casting.md
│   ├── die_casting.md
│   └── permanent_mold.md
│
└── papers/
    ├── key_findings/               # Extracted insights
    └── full_texts/                 # For deep reference
```

---

## Key Knowledge Files

### riser_design.md
```markdown
# Riser Design Rules

## Thumb Rules
- Riser height = 1.5 × riser diameter (cylindrical)
- Riser diameter ≥ 2 × riser neck diameter
- Riser modulus = 1.2 to 1.5 × casting modulus
- Minimum riser volume = 1.5 × shrinkage volume

## Neck Design
- Cylindrical riser: neck diameter = 0.6-0.8 × riser diameter
- Side riser: hemispherical bottom
- Top riser: straight neck, height = 15-30mm

## Placement
- Place at last-to-freeze region (maximum modulus)
- Distance from hot spot < feeding distance
- Avoid stress concentration areas
```

### feeding_distances.md
```markdown
# Feeding Distance by Material

## Formula
Feeding_distance = k × √(section_thickness_mm)

## k Values
| Material        | k   | Notes                    |
|-----------------|-----|--------------------------|
| Carbon steel    | 2.0 | Short, high shrinkage    |
| Stainless steel | 2.5 | Slightly better          |
| Gray iron       | 6.0 | Graphite expansion helps |
| Ductile iron    | 4.0 | Moderate expansion       |
| Aluminum A356   | 4.5 | Good fluidity            |
| Aluminum A380   | 4.0 | Higher Si, less fluid    |

## Practical Limits
- Steel: max 100mm even for thick sections
- Aluminum: max 150mm
- Iron: max 200mm (self-feeding)
```

### materials/steels.md
```markdown
# Carbon Steels

## 1045 (Medium Carbon)
- C: 0.42-0.50%
- Pouring temp: 1550-1600°C
- Liquidus: 1495°C
- Solidus: 1410°C
- Shrinkage: 3-4% by volume
- Fluidity at 1600°C: GOOD (300mm in 5mm section)
- Fluidity at 1550°C: FAIR (may misrun thin sections)

## Shrinkage Characteristics
- Liquid shrinkage: 1.0%
- Solidification shrinkage: 3.0%
- Solid shrinkage: 1.0%
- Total: ~5% (riser must compensate)

## Recommended Practice
- Multiple small risers better than one large
- Use chills to establish direction
- Pour quickly, keep sprue full
```

---

## CLI Tools for Claude

### Analysis Tools
```bash
# analyze-step
$ casting-analyze stepfile.stp
{
  "bounding_box": [100, 80, 60],
  "volume_mm3": 384000,
  "surface_area_mm2": 45200,
  "overall_modulus": 8.5,
  "sections": [
    {
      "id": 0,
      "location": [50, 40, 50],
      "thickness_mm": 25,
      "modulus": 12.5,
      "is_hot_spot": true
    }
  ],
  "risk_assessment": "MEDIUM"
}

# check-fluidity
$ casting-fluidity --material "steel_1045" --temp 1600 --section 5
{
  "fluidity_rating": "GOOD",
  "max_flow_distance_mm": 320,
  "fill_time_estimate_s": 3.2
}

# check-feeding
$ casting-feeding --from "50,40,50" --to "20,20,30" --material "steel_1045"
{
  "distance_mm": 85,
  "max_feeding_distance_mm": 56,
  "can_feed": false,
  "recommendation": "Add intermediate riser"
}
```

### CAD Modification Tools
```bash
# add-riser
$ casting-cad add-riser \
    --position "50,40,55" \
    --diameter 80 \
    --height 120 \
    --type "cylindrical"
Output: updated_model.step

# add-channel
$ casting-cad add-channel \
    --from "sprue" \
    --to "riser_1" \
    --diameter 40 \
    --type "runner"
Output: updated_model.step

# add-chill
$ casting-cad add-chill \
    --position "30,30,30" \
    --dimensions "20,20,10"
Output: updated_model.step

# modify-feature
$ casting-cad modify --id "riser_1" --diameter 90
Output: updated_model.step

# remove-feature
$ casting-cad remove --id "riser_2"
Output: updated_model.step
```

### Full Planning
```bash
# full-plan
$ casting-plan stepfile.stp --material "steel_1045" --process "sand"
{
  "analysis": {
    "hot_spots": 3,
    "max_modulus": 12.5,
    "risk_level": "MEDIUM"
  },
  "recommendations": {
    "risers": [
      {
        "position": [50, 40, 55],
        "diameter": 80,
        "height": 120,
        "reason": "Feeds hot spot 0, modulus 12.5"
      }
    ],
    "chills": [
      {
        "position": [30, 30, 30],
        "thickness": 12,
        "reason": "Accelerate freezing at transition"
      }
    ],
    "gating": {
      "sprue_diameter": 25,
      "fill_time_s": 4.5
    }
  },
  "expected_yield": 58,
  "confidence": "HIGH"
}
```

---

## Claude's System Prompt

```markdown
You are an expert casting engineer with 30 years of experience.
You have access to a knowledge base and analysis tools.

## Your Tools
- `analyze-step`: Get geometry data from STEP file
- `check-fluidity`: Determine if metal will flow to section
- `design-riser`: Size a riser for given modulus
- `check-feeding`: Verify feeding distance
- `cad add-riser`: Add riser to model
- `cad add-channel`: Add runner/sprue
- `cad add-chill`: Add chill
- `cad modify`: Change existing feature
- `full-plan`: Complete design recommendation

## How You Work
1. ALWAYS run `analyze-step` first to understand geometry
2. Ask user for material if not specified
3. Use thumb rules from knowledge base to reason
4. Call tools to get specific numbers
5. Use CAD tools to modify and show design
6. Explain your reasoning clearly
7. Show sketches/diagrams when helpful

## Your Tone
- Confident but cautious ("This should work, but watch for...")
- Educational ("The reason we do this is...")
- Practical ("In production, I'd also...")

## Key Principles
- Better safe than sorry (slightly oversized riser > defect)
- Directional solidification is king
- Feeding distance limits are real
- When in doubt, add a chill
```

---

## Example Conversation

```
User: bracket.step, steel, sand casting

Claude: Let me analyze this geometry first.

[runs: casting-analyze bracket.step]

I see a steel bracket with:
- Overall size: 120 x 80 x 40 mm
- Volume: 285,000 mm³
- 3 distinct sections

Section analysis:
- Boss A (center): 25mm thick, modulus 12.5 ← HOT SPOT
- Rib B (side): 8mm thick, modulus 4.0
- Base C (bottom): 12mm thick, modulus 6.0

The thick boss is your problem. For steel, modulus 12.5 means 
it needs a riser with modulus 15.6.

[runs: casting-riser --modulus 12.5 --material steel_1045]

Recommended: 80mm diameter x 120mm height cylindrical riser on top.

But wait - let me check if rib B can be fed from this riser.

[runs: casting-feeding --from "center" --to "rib_b" --material steel_1045]

Distance is 65mm, section is 8mm. Max feeding distance for steel 
at 8mm is only 56mm. 

This rib will have shrinkage porosity unless we add a side riser.

My plan:
1. Top riser on boss: 80mm dia (feeds main mass)
2. Side riser on rib: 50mm dia (feeds isolated section)
3. Chill at base corner to direct solidification upward

Expected yield: 52%
Risk: Low

Want me to add these to the model?

User: Yes

Claude: 
[runs: casting-cad add-riser --pos "50,40,55" --dia 80 --height 120]
[runs: casting-cad add-riser --pos "80,60,40" --dia 50 --height 75]
[runs: casting-cad add-chill --pos "30,30,30" --dim "15,15,10"]

Done. Here's your casting with risers and chill:

[3D view with everything shown]
- Original: gray
- Risers: blue
- Chill: orange

Yield: 51%
Confidence: HIGH

[Export STEP] [Export PDF report]
```

---

## Speed Comparison

| Step | MAGMA | MetalGPT |
|------|-------|----------|
| Import STEP | 1 min | 2 sec |
| Mesh | 5-30 min | N/A |
| Setup | 30 min | 2 min (chat) |
| Simulation | 1-4 hours | N/A |
| Iteration | Hours/days | Minutes |
| **Total** | **Days** | **Minutes** |

**Trade-off:**  
MAGMA = High accuracy, slow  
MetalGPT = Good enough, instant

---

## File Structure

```
metalGPT/
├── knowledge/
│   ├── core/
│   │   ├── chvorinov_rules.md
│   │   ├── feeding_distances.md
│   │   ├── riser_design.md
│   │   ├── gating_ratios.md
│   │   └── defect_modes.md
│   ├── materials/
│   │   ├── steels.md
│   │   ├── aluminum_alloys.md
│   │   ├── irons.md
│   │   └── superalloys.md
│   └── processes/
│       ├── sand_casting.md
│       ├── investment_casting.md
│       └── die_casting.md
│
├── tools/
│   ├── analyze_step.py
│   ├── check_fluidity.py
│   ├── check_feeding.py
│   ├── design_riser.py
│   ├── cad_modifier.py
│   └── full_plan.py
│
├── prompt.md                    # Claude's system prompt
├── demo/                        # Web UI
│   ├── index.html
│   └── app.js
│
└── README.md
```

---

## Next Steps

1. [ ] Curate knowledge base from papers/books
2. [ ] Build CLI tools (Python + OpenCascade)
3. [ ] Create Claude prompt with tool descriptions
4. [ ] Build simple web UI (3D viewer + chat)
5. [ ] Test with real casting examples
6. [ ] Iterate on knowledge base

---

## Key Principles

1. **No simulation** - Just knowledge + geometry
2. **Fast feedback** - Seconds, not hours
3. **Explainable** - AI shows its reasoning
4. **Interactive** - User approves/modifies
5. **Browser-based** - No install, shareable

---

*This is a thought experiment for building an AI-native casting design tool.*
