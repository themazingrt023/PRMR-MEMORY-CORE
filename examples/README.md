# PRMR Memory Core

PRMR Memory Core is an experimental memory architecture that represents information as:

- Origin
- Transformation
- Lineage
- Reconstruction

Instead of storing only snapshots of information, PRMR Memory stores how information changes over time.

## Core Hypothesis

Information can be represented as a chain of becoming:

Origin → Transformation → Reconstruction

This allows certain types of evolving information to be stored differently from traditional snapshot-based storage.

## Current Version

Current milestone: V0.12

## What Has Been Built

### V0.01 — Basic State Memory
Stored states and transitions.

### V0.02 — Causal Explanation
Added `why(state)` to explain why a state exists.

### V0.03 — Reconstruction
Added reconstruction from origin to final state.

### V0.04 — Text Engine
Represented text as origin + transformations.

### V0.05 — Text Benchmark
Compared full text snapshots against PRMR transformations.

### V0.06 — Image Engine
Represented simple SVG images as origin shapes + transformations.

### V0.07 — Video Engine
Represented simple SVG video frames as origin object + motion/colour/resize rules.

### V0.08 — Unified Lab
Combined core, text, image, and video tests into one lab report.

### V0.09 — SDK Structure
Created reusable package structure.

### V0.10 — Save / Load
Created `.prmr.json` memory files that can be saved and loaded.

### V0.11 — File Inspector
Added inspection tools for PRMR memory files.

### V0.12 — Compression Score
Added compression scoring against normal snapshot storage.

## V0.12 Results

### Text Compression Score
- Reconstruction match: True
- Normal storage: 109
- PRMR storage: 201
- Saved bytes: -92
- Result: PRMR used more storage

### Image Compression Score
- Reconstruction match: True
- Normal storage: 714
- PRMR storage: 481
- Saved bytes: 233
- Saved percentage: 32.63%
- Result: PRMR saved storage

### Video Compression Score
- Reconstruction match: True
- Normal storage: 7278
- PRMR storage: 602
- Saved bytes: 6676
- Compression ratio: 12.09x
- Saved percentage: 91.73%
- Result: PRMR saved storage

## Current Honest Claim

PRMR Memory does not prove infinite memory.

PRMR Memory does not currently beat modern compression systems like MP4, PNG, ZIP, or advanced databases.

The current claim is:

> PRMR Memory can represent structured evolving information as origin + transformations + lineage, and in early symbolic tests it can reconstruct final states while using less storage than snapshot-based storage.

## Strongest Early Domain

The strongest early result is video-like symbolic motion.

This suggests PRMR Memory may be useful for:

- Animation state storage
- Simulation history
- AI memory lineage
- Design versioning
- Company knowledge evolution
- Creative worldbuilding systems
- Structured visual transformation
- Recursive memory research

## File Format

PRMR files are saved as:

.prmr.json

These files store the origin state and transformation path required to reconstruct final information.

## Long-Term Vision

PRMR Memory Core aims to become a new representation layer for evolving information.

The long-term question:

> Can evolution itself become a storage primitive?

## Next Milestones

### V0.13
Document the project and define its positioning.

### V0.14
Add a stronger benchmark suite with larger tests.

### V0.15
Add multi-object image/video scenes.

### V0.16
Add timeline events and branching reconstruction.

### V0.17
Add PRMR file validation.

### V0.18
Add command-line tools.

### V0.19
Prepare public demo.

### V0.20
Package as early SDK prototype.