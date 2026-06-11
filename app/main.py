"""TTB Label Verification prototype — FastAPI backend.

Endpoints:
- GET  /api/applications/{app_number}  → application record (mock COLA lookup)
- POST /api/verify                     → per-field comparison results
- GET  /                               → single-page UI (static)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import ApplicationRecord, VerificationResponse
from .services.comparison import compare_all, summarize
from .services.extraction import get_extractor

APP_DIR = Path(__file__).parent
APPLICATIONS = json.loads((APP_DIR / "data" / "applications.json").read_text())

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp"}

app = FastAPI(title="TTB Label Verifier", version="1.0.0")
extractor = get_extractor()


@app.get("/api/applications/{app_number}", response_model=ApplicationRecord)
def get_application(app_number: str) -> ApplicationRecord:
    record = APPLICATIONS.get(app_number.strip().upper())
    if record is None:
        examples = ", ".join(sorted(APPLICATIONS)[:3])
        raise HTTPException(
            status_code=404,
            detail=f"Application '{app_number}' not found. Try one of the demo applications: {examples}.",
        )
    return ApplicationRecord(**record)


@app.post("/api/verify", response_model=VerificationResponse)
async def verify(
    application_number: str = Form(...),
    image: UploadFile = File(...),
) -> VerificationResponse:
    record = APPLICATIONS.get(application_number.strip().upper())
    if record is None:
        raise HTTPException(status_code=404, detail=f"Application '{application_number}' not found.")

    if image.content_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="Please upload a JPEG or PNG image of the label.")

    image_bytes = await image.read()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image is larger than 10 MB. Please upload a smaller file.")

    start = time.perf_counter()
    try:
        extracted = extractor.extract(image_bytes, image.content_type, filename=image.filename)
    except Exception as exc:  # surface provider errors as a friendly 502
        raise HTTPException(
            status_code=502,
            detail="The label could not be processed right now. Please try again.",
        ) from exc

    if not extracted.readable:
        raise HTTPException(
            status_code=422,
            detail=(
                "We couldn't read this image clearly. Please upload a sharper, "
                "straight-on photo of the label."
                + (f" ({extracted.notes})" if extracted.notes else "")
            ),
        )

    results = compare_all(record, extracted)
    return VerificationResponse(
        application_number=record["application_number"],
        results=results,
        summary=summarize(results),
        elapsed_seconds=round(time.perf_counter() - start, 2),
    )


# Serve the single-page UI.
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")

# Sample labels: any images placed in the repo's test_labels/ folder are
# listed in the UI so a label can be tried without uploading a file.
TEST_LABELS_DIR = APP_DIR.parent / "test_labels"
if TEST_LABELS_DIR.is_dir():
    app.mount("/test-labels", StaticFiles(directory=TEST_LABELS_DIR), name="test-labels")


@app.get("/api/test-labels")
def list_test_labels() -> list[dict[str, str]]:
    if not TEST_LABELS_DIR.is_dir():
        return []
    labels = []
    for path in sorted(TEST_LABELS_DIR.iterdir()):
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            words = path.stem.replace("_", " ").removeprefix("label ").strip()
            labels.append({"name": words.capitalize(), "filename": path.name, "url": f"/test-labels/{path.name}"})
    return labels


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(APP_DIR / "static" / "index.html")
