# UI Stitch Brief

## Product

GRACE Level-2 Pipeline desktop application for geodesy and hydrology researchers.

Core purpose:

- Configure a GRACE/GRACE-FO processing run
- Execute inversion and filtering workflows
- Run basin analysis and leakage correction
- Inspect stacks and generate quick plots

## Primary Users

- Research engineers maintaining the pipeline
- Domain scientists running batch experiments
- Students or analysts who need a safer guided interface instead of editing JSON directly

## Existing Functional Areas

- Common configuration
- Inversion and filtering
- Basin analysis
- Leakage correction
- Stack preview and plotting
- Run control, logging, progress, pause/stop

## Key User Flows

1. Load an existing JSON config
2. Inspect and update paths, time range, grid, and filter settings
3. Run full pipeline or a scoped run
4. Monitor logs and progress
5. Open stack data and preview a month/map
6. Export figures and basin/leakage outputs

## Information Architecture

- Dashboard / Home
  - project summary
  - current config
  - recent runs
  - run status
- Data & Paths
  - GFC input
  - output
  - DDK / AUX / boundary / low-degree / GIA / mascon references
- Processing Setup
  - time range
  - grid
  - inversion baseline
  - filters
- Leakage
  - scope
  - method
  - operator
  - FM / SF settings
- Basin
  - boundary file
  - basin selector
  - outputs
- Preview
  - stack file
  - region crop
  - projection
  - colormap
  - save figure
- Run Console
  - live log
  - progress
  - run / pause / stop

## Important Domain Constraints

- Input/output paths are critical and should be prominently visible
- Users often reuse JSON configs, so import/export config must be first-class
- HSAF has multiple strategies and parameter groups; those settings need progressive disclosure
- Leakage has two different mental models:
  - FM iterative correction
  - SF scale-factor correction
- Basin and leakage are optional scoped workflows and should not look mandatory
- Long-running jobs need strong status visibility and resumability cues
- Users need to understand local vs remote/HPC output routing

## UX Problems In Current UI

- Too many dense form fields on one screen
- Weak hierarchy between required inputs and advanced options
- Leakage settings are especially overloaded
- Plot and processing setup are mixed with too much raw parameter exposure
- State transitions are functional but not visually explicit enough

## Recommended Design Direction For Stitch

- Style:
  - scientific workstation
  - clean, light theme
  - high information density but with strong grouping
- Layout:
  - left navigation rail
  - top run/status bar
  - main content area with cards/sections
  - persistent log drawer or bottom console
- Interaction:
  - step-based setup for novice users
  - expert expandable panels for advanced parameters
  - scoped action buttons for `Full Run`, `Basin`, `Leakage`, `Preview`
- Visual priorities:
  - config source
  - current output root
  - active run state
  - warnings for missing inputs
  - advanced scientific parameters collapsed by default

## Screens To Ask Stitch To Generate

1. Main dashboard
2. Config and data-path setup
3. Processing and filters setup
4. Leakage workflow screen
5. Basin workflow screen
6. Preview/plot screen
7. Run monitor screen

## Information You Should Provide To Google Stitch

- product name:
  - GRACE Level-2 Pipeline
- platform:
  - desktop scientific application
- target users:
  - geodesy/hydrology researchers and pipeline engineers
- main tasks:
  - configure, run, inspect, export
- navigation model:
  - left navigation + main detail pane + bottom log console
- modules:
  - config
  - filters
  - leakage
  - basin
  - preview
  - run monitor
- important fields:
  - input data paths
  - output path
  - time range
  - grid resolution
  - Lmax
  - Gaussian/P4M6/DDK/FAN/HSAF options
  - leakage FM/SF options
  - basin boundary and output options
- critical actions:
  - load config
  - save config
  - run full
  - run basin
  - run leakage
  - plot
  - save plot
- system feedback:
  - live logs
  - progress bars
  - pause/stop
  - validation warnings
- tone:
  - precise
  - technical
  - research-oriented

## Suggested Prompt For Stitch

Design a desktop scientific workflow application called "GRACE Level-2 Pipeline" for researchers processing satellite gravity data. The product should support configuration-driven batch workflows, optional basin analysis, optional leakage correction, and stack preview plotting. Use a left navigation rail, a top execution status bar, a main content workspace with structured cards, and a bottom log console. Prioritize clarity for required inputs, progressive disclosure for advanced scientific parameters, and strong visibility of run state, warnings, and output locations. The UI should feel like a professional geoscience workstation rather than a generic consumer dashboard.
