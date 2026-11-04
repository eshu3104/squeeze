# Squeeze

Squeeze turns token-heavy inputs (slide decks, PDFs, web pages, JSON tool output) into compact, LLM-ready Markdown, and reports exactly how many tokens it saved.

Meta's **Muse Spark** reads every image and decides what it is worth: logos and stock photos are dropped, charts become data tables, diagrams and screenshots become short descriptions. A fidelity check, also run by Muse Spark, asks the same questions of the original and the compressed text, so the saving comes with proof that nothing important was lost.

> **Built during the Meta Global AI Developer Hackathon (Oct 26 – Nov 4, 2026).** All code in this repository was written during the event; the commit history shows it. Open-source libraries it depends on are listed in `pyproject.toml`.

## Status

Work in progress.
