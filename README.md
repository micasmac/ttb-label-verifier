# TTB Label Verifier (Prototype)

AI-assisted verification of alcohol beverage labels against their TTB applications. An agent enters an application number, uploads the label image, and gets a per-field checklist: ✅ Match, ❌ Mismatch, or ⚠️ Needs review. The agent makes the final call — the tool does the tedious matching.

Built per the V1 application spec: single-label verification, ~5-second results, a UI that needs zero training.

## Quick start

Requires Python 3.11+.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure (optional — see Demo mode below)
cp .env.example .env             # add your ANTHROPIC_API_KEY

# 4. Run
uvicorn app.main:app --reload
```

Open http://localhost:8000 and try application number `TTB-2026-0001` (Old Tom Distillery).

In VS Code: open the folder, select the `.venv` interpreter when prompted, and press F5 ("Run TTB Label Verifier" is preconfigured in `.vscode/launch.json`).

### Demo mode (V1 default)

V1 runs entirely in demo mode — no AI API key is used or required, so nothing sensitive is exposed in a public deployment. The demo extractor recognizes the bundled sample labels by filename and returns exactly the fields printed on each one (scripted fixtures), so every test case — wrong ABV, title-case warning, missing warning, blurry image — demonstrates its intended verification outcome through the real comparison logic. Any other uploaded image falls back to the Old Tom Distillery sample fields with a note explaining the image was not actually read.

Live AI extraction is planned for a future version. The complete Claude vision integration is already in the codebase as commented-out boilerplate — see `app/services/extraction.py` for the four activation steps (uncomment the class, uncomment `anthropic` in `requirements.txt`, set `ANTHROPIC_API_KEY`, enable the key check in `get_extractor()`).

### Test labels

The repo's `test_labels/` folder contains six generated label images, each targeting a specific acceptance criterion (correct label, title-case warning, all-caps brand, wrong ABV, missing warning + wrong volume, unreadable blur). The app serves this folder automatically: any images in it appear as a clickable sample gallery in Step 2, so the workflow can be demonstrated without uploading files. Regenerate or extend them with:

```bash
pip install pillow
python scripts/generate_test_labels.py test_labels
```

### Tests

```bash
pytest -v
```

The tests cover the comparison rules tied to the spec's acceptance criteria: case-difference brand names match, title-case government warnings are rejected, proof must equal 2 × ABV, volumes are unit-normalized, and unreadable fields surface as "needs review" rather than a guess.

## Approach

**Architecture.** FastAPI backend with two endpoints (`GET /api/applications/{number}`, `POST /api/verify`) and a dependency-free single-page UI served as a static file. Application records come from a seeded JSON dataset standing in for COLA, behind a simple lookup so a real COLA API could replace it without touching anything else.

**AI for extraction, code for judgment.** The design calls for one multimodal model call extracting the label's text as structured JSON (a single call keeps latency near the 5-second target from the discovery interviews). In V1 this layer is stubbed with a demo extractor to avoid exposing an API key in a public demo; the live integration ships as ready-to-activate commented boilerplate. All comparison is deterministic Python: the strict government-warning check, ABV/proof math, and volume normalization are rules, not model output. This makes the strict checks predictable and testable, and confines the AI to the task it's good at — reading the image.

**Matching philosophy** (taken directly from the stakeholder interviews):
- "STONE'S THROW" vs "Stone's Throw" → match, with a note about the formatting difference (Dave's example — trivial differences shouldn't be false mismatches).
- The government warning is zero-tolerance: exact statutory wording, "GOVERNMENT WARNING:" in all caps (Jenny's title-case rejection example).
- Anything the extractor couldn't read → "needs review," never a silent guess.

**UI.** One page, three numbered steps, large controls, system fonts only (the TTB firewall blocks many outbound domains, so nothing depends on a CDN). The results are styled as a checklist — a digital version of the printed checklist agents keep on their desks today.

## Assumptions and trade-offs

- **Mock COLA data.** COLA integration was explicitly out of scope; 5 seeded applications (`TTB-2026-0001`–`0005`) demonstrate the automated-retrieval pattern.
- **Bold detection.** Whether "GOVERNMENT WARNING:" is bold can't be reliably determined from a photo; the result notes this for visual confirmation.
- **Single front-facing label image** per application. Multi-panel labels (front + back) are future work.
- **No persistence or auth.** Nothing is stored beyond the request; the prototype handles no sensitive data.
- **No live AI in V1.** To avoid exposing an API key behind a public demo, extraction is stubbed; uploaded images are not actually scanned in this version. The live integration is included as commented-out boilerplate, and the extractor sits behind a small interface (`LabelExtractor`) so a self-hosted model could also be swapped in for any deployment inside TTB's restricted network.
- **Batch upload deferred.** The biggest stakeholder ask after core verification, deliberately left out to keep V1 simple; the per-request design (stateless `POST /verify`) extends naturally to a queue.

## Deployment

The repo includes a `render.yaml` Blueprint for [Render](https://render.com)'s free tier:

1. Push the repo to GitHub.
2. In the Render dashboard: **New +** → **Blueprint** → select the repo.
3. Render reads `render.yaml` and deploys automatically; you get a public `https://ttb-label-verifier.onrender.com`-style URL. Pushes to the default branch redeploy automatically.

Free-tier note: the service spins down after ~15 minutes of inactivity, and the first request afterward can take up to a minute while it wakes. This is platform behavior, not the app — once warm, verification responds well under the 5-second target. Hit the URL once before a demo to warm it up.

## Project structure

```
app/
  main.py                 FastAPI app and endpoints
  models.py               Pydantic models
  data/applications.json  Seeded mock COLA records
  services/
    extraction.py         AI label extraction (Anthropic / demo fallback)
    comparison.py         Deterministic field-matching rules
  static/index.html       Single-page UI
tests/
  test_comparison.py      Unit tests for the matching rules
```
