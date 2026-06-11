# Application Specification — AI-Powered Alcohol Label Verification App

**Version:** 1.0 (Prototype)
**Date:** June 11, 2026
**Status:** Draft for take-home implementation
**Context:** TTB Compliance Division proof-of-concept. Standalone prototype — no COLA integration.

---

## 1. Purpose

TTB agents review ~150,000 label applications per year, and much of that review is routine field matching: confirming that the brand name, alcohol content, and other values on the label artwork match what was entered in the application. This prototype lets an agent upload a label image alongside the application data and uses AI to extract the label's text and compare it to the application, returning a clear match/mismatch result per field. The agent makes the final call; the tool does the tedious matching.

## 2. Goals and Non-Goals

### Goals (V1)
- Verify a **single label** against a **single application** per submission.
- Extract label text from an uploaded image using AI (vision model or OCR + LLM).
- Compare five core fields and report per-field results: match, mismatch, or needs review.
- Return results in roughly **5 seconds or less** (the prior vendor pilot failed at 30–40s and agents abandoned it).
- A UI simple enough for low-tech-comfort users: one screen, obvious buttons, no hunting.

### Non-Goals (V1 — documented as future work)
- Batch upload of 200–300 applications (high-value future feature; out of scope per "keep it simple").
- COLA system integration (explicitly excluded by IT).
- Correction of badly photographed labels (severe angles, glare, poor lighting). V1 should *detect* an unreadable image and tell the agent, not silently fail.
- User accounts, authentication, persistence of results, or audit trail.
- Production-grade federal compliance (FedRAMP, PII handling). Prototype only; no sensitive data stored.

## 3. Users

Primary user: a TTB compliance agent. The user base ranges from 28-year veterans with low tech comfort to recent graduates. Design benchmark from the stakeholder: "something my 73-year-old mother could figure out." This drives every UX decision — large controls, plain language, one obvious workflow, results readable at a glance.

## 4. Core Workflow

1. Agent opens the app (single page).
2. Agent enters the **application number**. The app retrieves that application's record and displays the fields to be verified against the label: brand name, class/type, alcohol content, net contents (the government warning is a fixed regulatory text, so it is checked automatically and shown as a fifth checklist item). For the prototype, application records come from a seeded mock dataset standing in for COLA, since direct COLA integration is out of scope.
3. Agent uploads the label image (JPEG/PNG, drag-and-drop or file picker).
4. Agent clicks **Verify Label**.
5. App extracts text from the image and compares each field, showing a progress indicator.
6. Results appear as a per-field checklist: ✅ Match / ❌ Mismatch / ⚠️ Needs review, with the application value and the extracted label value shown side by side for every field.
7. Agent reviews and proceeds (V1 does not record a decision; the output is the comparison itself).

## 5. Fields Verified

| Field | Comparison rule |
|---|---|
| Brand name | Case-insensitive, punctuation-tolerant match. "STONE'S THROW" vs "Stone's Throw" → **Match** (flagged as a minor formatting difference, not a mismatch). |
| Class/type designation | Case-insensitive match (e.g., "Kentucky Straight Bourbon Whiskey"). |
| Alcohol content | Numeric comparison of ABV; tolerant of formatting ("45% Alc./Vol.", "45% ABV", "90 Proof" → 45%). Proof, if present, must equal 2× ABV. |
| Net contents | Numeric + unit comparison ("750 mL", "750ml" → equal). |
| Government Health Warning | **Strict.** Must match the statutory text word-for-word, and "GOVERNMENT WARNING:" must appear in ALL CAPS. Title case, paraphrasing, or altered wording → **Mismatch** with the specific deviation highlighted. (Bold-font detection is best-effort from an image and noted as a limitation.) |

The matching philosophy follows the agents' own judgment: trivial formatting differences should not generate false mismatches (Dave's "STONE'S THROW" example), but the government warning gets zero tolerance (Jenny's title-case rejection example). Anything the AI is uncertain about is surfaced as **Needs review** rather than guessed — the tool assists, it does not decide.

## 6. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | Lookup by application number returning the application's fields to verify (served from a seeded mock dataset standing in for COLA; includes the Old Tom Distillery sample for demo) | Must |
| FR-1a | Clear, non-blocking error when an application number is not found, with an example of a valid demo number | Must |
| FR-2 | Image upload (JPEG/PNG, max ~10 MB) with preview | Must |
| FR-3 | Label text extraction behind a swappable interface. V1: demo extractor returning sample data (no AI API key exposed); live AI extraction included as commented-out boilerplate for a future version | Must |
| FR-4 | Per-field comparison with Match / Mismatch / Needs review status and side-by-side values | Must |
| FR-5 | Strict government-warning validation with deviation highlighting | Must |
| FR-6 | Graceful handling of unreadable/irrelevant images: clear message asking for a better image (mirrors current agent practice) | Must |
| FR-7 | Loading state during processing; clear error message on API failure or timeout | Must |
| FR-8 | Overall summary verdict (e.g., "4 of 5 fields match — review government warning") | Should |

## 7. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | End-to-end verification result in ≤ ~5 seconds for a typical label; hard timeout with a friendly message at ~15 seconds |
| NFR-2 | UI usable with zero training: one page, one primary action, results readable at a glance |
| NFR-3 | Works in a modern browser on desktop; no install |
| NFR-4 | No data persisted server-side beyond the request lifecycle (prototype handles nothing sensitive) |
| NFR-5 | Deployed and publicly accessible at a URL for evaluation |

## 8. Architecture (Proposed)

- **Frontend:** single-page web app (e.g., React) — application-number lookup, retrieved-fields display, image upload, results checklist.
- **Backend:** thin API service (e.g., Python/FastAPI or Node) with two endpoints: `GET /applications/{app_number}` returning the application record, and `POST /verify` accepting the image + application number, returning per-field results as JSON.
- **Mock data store:** a small seeded set of application records (JSON or SQLite) keyed by application number, simulating COLA data. The lookup sits behind its own interface so a real COLA API could replace it later without touching the rest of the app.
- **AI layer:** **stubbed in V1.** To avoid exposing an AI API key behind a publicly deployed demo, V1 ships with a demo extractor that uses scripted fixtures: the bundled test labels are recognized by filename and return exactly the fields printed on each, so every verification outcome (match, ABV mismatch, strict-warning rejection, unreadable image) is demonstrable through the real comparison logic without any external API call. Other images fall back to sample data with a note that the image was not actually read. The complete live integration — a multimodal vision LLM call returning structured JSON (a single call keeps latency near the 5-second target) — is included in the codebase as commented-out, ready-to-activate boilerplate (`app/services/extraction.py`), with activation steps documented in the code, `requirements.txt`, and `.env.example`. Live AI extraction is planned for a future version. Deterministic comparison logic remains in code regardless — the strict warning check and numeric ABV/contents checks are rule-based, not left to the model.
- **Note on the firewall constraint:** TTB's network blocks many outbound domains, which killed cloud features in the prior pilot. For this prototype a cloud AI API is acceptable, but the AI layer should sit behind a small abstraction so a self-hosted model (e.g., local OCR + open-weights LLM) could be swapped in for any production path. This is documented as a known deployment constraint rather than solved in V1.

## 9. Error Handling

- Unknown application number → "Application TTB-2026-XXXX not found. Try one of the demo applications: …"
- Image unreadable / not a label → "We couldn't read this image clearly. Please upload a sharper, straight-on photo of the label." (matches current agent workflow of requesting a better image)
- AI uncertain on a field → field marked **Needs review** with whatever was extracted, never a silent guess
- API timeout/failure → plain-language error with a retry button
- Missing application number or no image → inline validation before submission

## 10. Assumptions

- Although COLA access is restricted, this proof of concept is designed as an example of automating data retrieval in the agent verification process.
- To avoid exposing an AI API key in the deployed demo, V1 uses a demo extractor in place of live AI image scanning; the live integration is included as commented-out boilerplate and is planned for a future version.
- Application data is served from a seeded mock dataset (5–10 records) keyed by application number, standing in for COLA; no live COLA access.
- One label image per application; multi-panel labels (front + back) are out of scope for V1.
- English-language labels.
- The statutory government warning text is hardcoded as the comparison reference.
- Test labels will be created with AI image generation (per the brief) plus the provided sample (Old Tom Distillery bourbon).

## 11. Deliverables

- Source code repository with README (setup, run instructions, approach, tools, assumptions, trade-offs).
- Deployed working prototype at a public URL.

## 12. Acceptance Criteria (V1 Done)

- Entering a valid demo application number displays its fields; the sample label (Old Tom Distillery) then verifies correctly across all five fields in ≤ ~5 seconds.
- An unknown application number produces a clear error with valid demo numbers suggested.
- A label with a title-case government warning is flagged as a mismatch with the deviation shown.
- A brand-name case difference (STONE'S THROW vs Stone's Throw) is reported as a match, not a false mismatch.
- An unreadable image produces a helpful message, not a crash or a wrong answer.
- A first-time user can complete a verification with no instructions.

## 13. Future Considerations (Explicitly Deferred)

- **Live AI extraction** — activate the included Anthropic vision integration (commented-out boilerplate in `app/services/extraction.py`) with secure server-side key management, so uploaded label images are actually scanned rather than answered from demo data.
- **Batch upload** — process 200–300 applications at once with a results queue (top stakeholder ask after core verification).
- Image preprocessing for angled/glary/poorly lit photos.
- Beverage-type-specific rule sets (beer/wine/spirits variations, bottler name/address, country of origin).
- Result persistence, agent decision recording, and export.
- Self-hosted AI deployment to satisfy the network/firewall constraint; FedRAMP-aligned production hardening.
