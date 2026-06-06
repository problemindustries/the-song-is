# The Song Is

Visual project browser for FL Studio and Ableton Live producers.

**[thesong.is](https://thesong.is)** — download the app (newsletter required)

## What it does

Scan your projects folder, display each project as a draggable card on a freeform canvas. Rate, colour-tag, annotate, and open projects directly in FL Studio or Ableton Live. Sticky notes on the canvas. Everything persists locally — no server, no accounts, no data leaves your device.

## Running locally

```bash
pip install -r app/requirements.txt
python app/app.py
```

Requires Python 3.9+.

## Building

Builds are produced by GitHub Actions on tag push — see `.github/workflows/release.yml`.

## Privacy

- No network requests, ever
- No login, no accounts
- All metadata stored at `~/Library/Application Support/The Song Is/data.json` (Mac) or `%APPDATA%\The Song Is\data.json` (Windows)
- Read-only access to your projects folder

## License

MIT
