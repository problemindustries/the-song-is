# The Song Is

Visual project browser for FL Studio and Ableton Live producers.

**[thesong.is](https://thesong.is)**

![The Song Is — canvas view](app/static/screenshot_01.png)
![The Song Is — project detail](app/static/screenshot_02.png)

## Features

- Scan your projects folder, display each project as a draggable card on a canvas. 
- Rate, colour-tag, write notes about each project
- Open projects directly from the app
- Add sticky notes
- Everything persists locally, no account required
- Make a backup and export your data anytime
- Supports FL Studio & Ableton Live 

## Running locally

```bash
pip install -r app/requirements.txt
python app/app.py
```

Requires Python 3.9+.

## Building

Builds are produced by GitHub Actions on tag push — see `.github/workflows/release.yml`.

## License

GPL v3 — see [LICENSE](LICENSE).
