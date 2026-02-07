# Integration Memory - Facebook Scraper

Last updated: 2026-02-07

## Current State

**Branch:** `working_step1_dom_feature_ensemble` (6 commits ahead of main)
**Status:** Project paused, recently initialized with Claude Code tooling

## What Was Done This Session

1. **Created CLAUDE.md** - Full project configuration for Claude Code
2. **Cleaned up .tmp.driveupload/** - Removed 2,825 temp files (241 MB) from git tracking and disk
3. **Updated .gitignore** - Added `.tmp.driveupload/`, `venv_scraper/`, `models/**/*.pkl`
4. **Code health assessment** - Full audit of dependencies, imports, models, config

## Code Health Summary

| Area | Status | Notes |
|------|--------|-------|
| Dependencies | Needs fix | `asyncpg` missing from requirements.txt |
| Imports | Good | All cross-module references resolve |
| Models | Good | Trained on 30 samples - possible overfitting |
| Config/.env | Good | All env vars set |
| Virtual Env | Good | Python 3.11.9 |
| Tests | Empty | `tests/` directory has no tests |

## Known Issues (Priority Order)

1. **CRITICAL**: `asyncpg` not in `requirements.txt` - metrics_tracker.py will fail at runtime
2. **HIGH**: Debug print statements in `fb_scraper.py` lines 35-36 ("BULLETPROOF VERSION LOADED")
3. **HIGH**: `fb_scraper.py` is ~6,200 lines - needs refactoring
4. **MEDIUM**: Hardcoded Windows Chrome/Edge paths (~line 4526)
5. **MEDIUM**: Diagnostic debug code left in production paths
6. **LOW**: Model trained on only 30 samples (9 test) - verify not overfitting

## Architecture Quick Reference

**3-Layer Detection:**
1. Structural/DOM analysis
2. ML Ensemble (RandomForest + GradientBoosting + XGBoost + MLP)
3. LLM Fallback (GPT-3.5-turbo)

**Key Files:**
- `fb_scraper.py` - Main orchestrator
- `src/ml_scraper.py` - 3-layer detection engine
- `src/dom_ensemble.py` - ML ensemble classifier
- `src/llm_classifier.py` - OpenAI integration
- `src/sold_item_detector.py` - Sold item patterns
- `src/resources/fb_groups.py` - 6 target Facebook groups

## Pre-existing Uncommitted Changes

These files had modifications before this session (NOT our changes):
- `fb_scraper.py` - modified (pre-existing)
- `src/ml_scraper.py` - modified (pre-existing)
- `src/utils.py` - modified (pre-existing)
- `src/metrics_tracker.py` - untracked (new file)
- `fbscraper-project-description.md` - untracked
- `logs/` - untracked

## Next Steps (When Resuming)

1. Add `asyncpg` to `requirements.txt`
2. Remove debug print statements from `fb_scraper.py`
3. Review pre-existing uncommitted changes in `fb_scraper.py`, `ml_scraper.py`, `utils.py`
4. Add basic test coverage
5. Consider refactoring `fb_scraper.py` into smaller modules
6. Decide whether to merge to main or continue on feature branch
