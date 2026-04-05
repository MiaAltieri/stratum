Stratum is a read-only local file-system scanner that detects duplicate files and writes advisory suggestions to a structured JSONL log. It never modifies, moves, or deletes any file — all suggested actions are yours to review and act on manually.

```bash
poetry install
cp config/stratum.toml.example ~/.stratum/stratum.toml
poetry run stratum
```
