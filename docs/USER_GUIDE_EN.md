# Universal Document OS — User Guide (English)

**Version:** v4.2.0 · **Audience:** end users of the web panel (no technical background required)
**Install first?** See [INSTALL.md](../INSTALL.md). This guide assumes the app is already running at <http://localhost:8000>.

---

## 1. What this app does

You put a document in, you get its text out — on your own computer. Concretely it can:

- **Read** PDF, Word (DOCX), Excel (XLSX), PowerPoint (PPTX), OpenDocument (ODT/ODS/ODP), plain text, Markdown, CSV, JSON, HTML and RTF files.
- **Read images** (JPG/PNG/WEBP/TIFF) with **real OCR** — the Docker image ships Tesseract with English + Persian.
- **Show** the detected format, how much text was found, a preview, and smart analysis (language, direction, document category).
- **Export** the extracted text as `.txt`/`.md`, or rendered `.html` from Markdown sources.
- **Remember** every job: each upload creates a workroom record, a row in the SQLite job store, and an audit-log entry.
- **Show a live Smart Dashboard** (panel → Dashboard tab): engine availability, counters, storage and security posture — all measured, nothing invented.

What it does **not** do yet (honest list): translation through the UI, automatic notifications, login/accounts. Those are planned — see [ROADMAP.md](../ROADMAP.md).

## 2. Opening the app

| Page | URL | Use |
|---|---|---|
| Landing | <http://localhost:8000> | Overview + link to the panel |
| Panel | <http://localhost:8000/app> | Where you actually work with documents |
| Health | <http://localhost:8000/api/health> | If unsure it's alive — should show `{"status":"ok", …}` |

No username or password is needed; the app is local-only by design.

## 3. Processing a document — step by step

1. Open <http://localhost:8000/app>.
2. Click **Choose file** and pick a document (max 25 MB by default).
3. Pick an **operation**:
   - **Analyze** — just extract text and show results.
   - **Export text / Copy** — also create a downloadable file.
4. If exporting, choose the **target format**: `txt` or `md`.
5. Press **Process**. Within seconds you'll see:
   - detected format (e.g. `PDF`),
   - size and character count,
   - a text preview,
   - a **Download** link when an export was produced.

### Reading the result fields

| Field | Meaning |
|---|---|
| `job_id` | Unique id of this run — use it to find the record later |
| `detected_format` | What the app thinks the file is (by extension, then MIME guess) |
| `characters` | How many characters of text were extracted |
| `status` | `ANALYZED` = recorded only; `READY` = a download file exists |
| `preview` | First ~5000 characters of the extracted text |

## 4. Understanding common messages

The app never crashes on a bad file — it tells you what happened instead:

| Message you see | What it means | What to do |
|---|---|---|
| `[UNSUPPORTED_FORMAT] ...` | Legacy Office file (XLS/PPT), or missing helper (`antiword` for DOC), or an image without an installed OCR engine | Re-save as DOCX/XLSX/PPTX; install the named tool; for OCR run the Docker image or install tesseract |
| `[EXTRACTION_ERROR] ...` | File is corrupt, password-protected | Remove any password / re-save the file |
| `content rejected (415)` | Content does not match the extension (e.g. an exe named .pdf) or an archive bomb | Send the genuine file |
| Empty text from a PDF | It's a *scanned* (image-based) PDF — the text layer is empty | OCR of rendered PDF pages is planned (roadmap); extract the page images and upload them instead |
| "file too large" | Upload above the 25 MB limit | Split/compress the file, or raise `MAX_UPLOAD_BYTES` in `.env` |

## 5. Where your data lives

Everything stays inside the project folder:

```
data/uploads/    ← your original files (named by job id)
data/outputs/    ← exported .txt/.md/.html files
data/workrooms/  ← one JSON record per job
data/audit.jsonl ← append-only history of all jobs
data/jobs.db     ← durable SQLite job store
```

Deleting a job's files removes it completely; `./backup.sh` archives this whole folder (with secret values redacted from the settings snapshot). Nothing is sent to the internet during normal use.

## 6. Keyboard-free daily routine

```bash
./start.sh     # morning: turn on
./status.sh    # is everything ok?
./logs.sh      # anything weird?
./stop.sh      # evening: turn off
./update.sh    # when a new release appears
```

Windows: double-click the matching `.bat` files.

## 7. FAQ

**Can I use it from my phone?** The panel is responsive and PWA-installable (Add to Home screen); open `http://<your-computer-ip>:8000/app` on the same Wi-Fi (and keep in mind there's no login unless the admin sets `UDO_API_KEYS` — trusted networks only).

**Is there a limit on file size?** Yes, 25 MB by default, configurable via `MAX_UPLOAD_BYTES`.

**Did my upload go anywhere online?** No. Processing is entirely local.

**Why did a download link fail with 404?** Exported files live in `data/outputs/`; if they were deleted or the name was mistyped, the app safely answers 404 without revealing why.

**Can multiple people use it?** Technically yes on a shared network, but without accounts/permissions today — treat it as single-user until auth ships (v4.0 roadmap).

---

*Persian version of this guide: [USER_GUIDE_FA.md](USER_GUIDE_FA.md). Technical details: [docs/API.md](API.md).*
