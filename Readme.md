# SLV Trading Assistant

A modular Python research assistant and signal generator for trading the **SLV silver ETF**. Collects price data, macro-economic indicators, and news headlines, analyses them together, and produces an explainable 11-section research report with a trade signal, confidence score, entry/stop/target levels, and risk warnings.

**Decision support only — does not place trades. All output is research, not financial advice.**

---

## Quick Start

```bash
cd SLV_Trading_Assistant
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys
python main.py
```

See [`SLV_Trading_Assistant/README.md`](SLV_Trading_Assistant/README.md) for full documentation: installation, first-time Schwab OAuth setup, CLI reference, report sections, trading style profiles, data sources, and Windows Task Scheduler setup.

---

## Repository Layout

```
SLV_Trading_Assistant/   # Main Python package — entry point, modules, tests, config
SLV Modular System Architect & Sub-Agent.md         # Architecture design document
SLV Modular System Architect & Sub-Agent Plan Implementation.md  # Implementation plan
reference-and-read-the-virtual-tulip.md             # Reference notes
```
