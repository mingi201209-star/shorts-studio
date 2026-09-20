# shorts-studio

Independent 9:16 Shorts production engine. TTS speech timing is the source of truth for captions; rendering and QA are kept separate from `shorts-bot`.

## Quick start

```bash
pip install -e '.[dev]'
python -m shorts_studio validate examples/comet.json
python -m shorts_studio render examples/comet.json --dry-run
pytest
```

A full render requires FFmpeg and TTS/network access. CI smoke mode uses deterministic local timing so it does not depend on paid APIs.

## Safety boundary

This repository does not upload to YouTube and does not modify `shorts-bot`.

## Status

V1 bootstrap. See the feature PR for verified tests, smoke-render status, and known limitations.
