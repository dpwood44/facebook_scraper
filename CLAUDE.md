# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Facebook Group Scraper for GI Joe Collectible Sales - an ML-enhanced web scraper that intelligently extracts sales posts from multiple Facebook collector groups using a 3-layer detection system: structural/DOM analysis, ML ensemble models, and LLM fallback classification.

**Tech Stack:** Python 3.x, Playwright, scikit-learn, XGBoost, OpenAI (GPT-3.5-turbo), BeautifulSoup4, asyncpg, loguru

**Status:** This is an older project on the `working_step1_dom_feature_ensemble` branch. The ML ensemble and LLM integration were in active development. ~80% effectiveness achieved on two groups before work paused.

## Common Commands

### Environment Setup
```powershell
# Activate virtual environment
.\venv_scraper\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install
```

### Running the Scraper
```powershell
# Main scraper entry point
python fb_scraper.py
```

### Model Training
```powershell
# Train DOM ensemble models from labeled data
python model_training_script.py
```

### Testing
```powershell
# Run tests (test directory exists but is currently empty)
pytest tests/ -v
```

### Debugging
```powershell
# Verify module imports
python import_test.py

# Debug LLM initialization
python debug_llm.py
```

## Architecture

### 3-Layer Detection System
```
Layer 1: Structural Detection
  └── Analyzes DOM patterns, HTML size, element counts

Layer 2: DOM ML Ensemble (VotingClassifier)
  ├── RandomForestClassifier
  ├── GradientBoostingClassifier
  ├── XGBoost
  └── MLP Neural Network

Layer 3: LLM Fallback
  └── GPT-3.5-turbo for boundary cases & consensus verification
```

### Feature Extraction (45+ features)
- Basic DOM counts (divs, spans, links, images, buttons)
- Facebook-specific patterns (profile links, reactions, timestamps)
- Content analysis (price patterns, sale keywords, GI Joe terms)
- Text metrics (capitalization, word count, sentence count)
- Structure complexity (nesting depth, CSS classes, data attributes)

### Key Source Files
| File | Purpose |
|------|---------|
| `fb_scraper.py` | Main scraper orchestrator (~6,200 lines) |
| `src/ml_scraper.py` | 3-layer detection engine with feedback learning |
| `src/dom_ensemble.py` | ML ensemble classifier (RF, GB, XGB, MLP) |
| `src/sold_item_detector.py` | Pattern-based sold item detection |
| `src/training_manager.py` | Training data collection & labeling interface |
| `src/llm_classifier.py` | OpenAI GPT-3.5-turbo async integration |
| `src/metrics_tracker.py` | PostgreSQL async metrics tracking |
| `src/utils.py` | Enhanced logging & helper functions |
| `src/resources/fb_groups.py` | Target group configurations (6 groups) |

### Data Flow
1. **Scrape**: Playwright navigates Facebook groups, extracts post HTML
2. **Detect**: 3-layer system classifies posts as sale/not-sale
3. **Analyze**: Sold item detector checks posts & comments for completion signals
4. **Export**: Results saved to CSV/JSON in session-specific output directories
5. **Learn**: Feedback collected for model retraining

### Output Organization
```
scrapes/fb_group_scrape_YYYYMMDD_HHMMSS/
├── logs/                          # Session debug log
├── training_data/                 # Labeling interface HTML
├── collected_posts.csv            # Main export
├── collected_posts.json           # Structured data
├── sold_items_analysis.json       # Sold detection results
└── feedback_*.json                # Human feedback for retraining
```

### Pre-trained Models
```
models/dom_ensemble/
├── ensemble_model.pkl             # Voting ensemble
├── scaler.pkl                     # Feature scaler
├── training_data.pkl              # Training examples
└── training_metrics.json          # Performance metrics
```

## Environment Variables

Key variables in `.env`:
- `FACEBOOK_EMAIL`, `FACEBOOK_PASSWORD` - Facebook login credentials
- `OPENAI_API_KEY` - GPT-3.5-turbo API key
- `DB_NAME`, `DB_USER`, `DB_PASSWORD` - PostgreSQL metrics database
- `CHROME_DEBUG_PORT`, `CHROME_PROFILE_PATH` - Browser automation config

**Warning:** Never commit `.env` or files containing credentials.

## Import Conventions

Imports use the `src.` prefix for project modules:
```python
from src.ml_scraper import MLScraper
from src.dom_ensemble import DOMEnsembleClassifier
from src.sold_item_detector import SoldItemDetector
from src.llm_classifier import LLMClassifier
from src.utils import setup_logging
```

## Target Facebook Groups

Configured in `src/resources/fb_groups.py`:
1. G.I. Joe BST Vault
2. GI Joe ARAH Vintage (1982-1994)
3. PRO JOE
4. G.I. Joe O-Rings
5. DEAL/NO DEAL
6. GI Joe Trader PX

## Key Patterns

- **Async/Await**: Heavy use of `asyncio` throughout (Playwright, OpenAI, database)
- **Session Isolation**: Each scrape gets unique session ID and output directory
- **Dual Logging**: Console (concise via loguru) vs File (comprehensive) logging
- **Feedback Loop**: Training data collected during scraping for continuous model improvement
- **Graceful Fallbacks**: Each detection layer falls back to the next on failure

## Known Issues & Context

- The main scraper file (`fb_scraper.py`) is very large (~6,200 lines) - consider refactoring
- ARAH Group had post-skipping issues (commit `20042a2d`)
- Tests directory exists but is empty - needs test coverage
- The `.tmp.driveupload/` directory contains many deleted temp files (safe to clean up)
- Branch `working_step1_dom_feature_ensemble` was the active development branch

## Related Projects

- `c:\Projects\tcp_ebay_scraper` - GI Joe eBay scraper with full ML classification pipeline
- `c:\Projects\gi_joe_ai_unified` - Unified GI Joe AI classification system

## Skills Files

When working on this project, read relevant skills from `~/.claude/skills/`:
- `gi-joe-domain.md` - GI Joe collectible domain knowledge
- `ml-classification.md` - ML training, ensemble config, data prep
