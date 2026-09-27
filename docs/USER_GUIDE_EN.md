# Universal Document OS — User Guide (English)

**Version:** v3.2.5 · **Audience:** end users of the web panel (no technical background required)
**Install first?** See [INSTALL.md](../INSTALL.md). This guide assumes the app is already running at <http://localhost:8000>.

---

## 1. What this app does

You put a document in, you get its text out — on your own computer. Concretely it can:

- **Read** PDF, Word (DOCX), Excel (XLSX), PowerPoint (PPTX), OpenDocument Text (ODT), plain text, Markdown, CSV, JSON, HTML and RTF files.
- **Show** what format was detected, how much text was found, and a preview of that text.
- **Export** the extracted text as a `.txt` or `.md` file you can download.
- **Remember** every job: each upload creates a record (a "workroom") plus an entry in an audit log, so nothing disappears silently.

What it does **not** do yet (honest list): OCR for scanned/image PDFs, translation through the UI, login/accounts. Those are planned — see [ROADMAP.md](../ROADMAP.md).

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
| `[UNSUPPORTED_FORMAT] ... convert to DOCX` | Legacy Office file (DOC/XLS/PPT/ODS/ODP) | Re-save as DOCX/XLSX/PPTX and upload again |
| `[EXTRACTION_ERROR] ...` | File is corrupt, password-protected, or a helper library is missing | Remove any password / re-save the file; ask your admin to install optional libraries |
| Empty text from a PDF | It's a *scanned* (image-based) PDF — no text layer | OCR support is coming (roadmap); meanwhile try Adobe/Preview "export as text" if available |
| "file too large" | Upload above the 25 MB limit | Split/compress the file, or raise `MAX_UPLOAD_BYTES` in `.env` |

## 5. Where your data lives

Everything stays inside the project folder:

```
data/uploads/    ← your original files (named by job id)
data/outputs/    ← exported .txt/.md files
data/workrooms/  ← one JSON record per job
data/audit.jsonl ← append-only history of all jobs
```

Deleting a job's files removes it completely; backups copy this whole folder (`./backup.sh`). Nothing is sent to the internet during normal use.

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

**Can I use it from my phone?** The panel is responsive; open `http://<your-computer-ip>:8000/app` on the same Wi-Fi (and keep in mind there's no login — trusted networks only).

**Is there a limit on file size?** Yes, 25 MB by default, configurable via `MAX_UPLOAD_BYTES`.

**Did my upload go anywhere online?** No. Processing is entirely local.

**Why did a download link fail with 404?** Exported files live in `data/outputs/`; if they were deleted or the name was mistyped, the app safely answers 404 without revealing why.

**Can multiple people use it?** Technically yes on a shared network, but without accounts/permissions today — treat it as single-user until auth ships (v4.0 roadmap).

---

*Persian version of this guide: [USER_GUIDE_FA.md](USER_GUIDE_FA.md). Technical details: [docs/API.md](API.md).*
