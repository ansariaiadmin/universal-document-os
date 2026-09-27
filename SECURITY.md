# Security Policy — Universal Document OS

**Applies to:** v3.2.4 and later · **Language of this doc:** English (Persian summary at the end)

---

## Supported versions

| Version | Supported | Notes |
|---|---|---|
| 3.2.x | ✅ | Current hardening baseline |
| < 3.2 | ❌ | Upgrade before reporting issues against them |

---

## Reporting a vulnerability

**Please do not open a public issue.** Use one of:

- GitHub private advisory: <https://github.com/ansariaiadmin/universal-document-os/security/advisories/new>
- Email: `security@ansariaiadmin.dev`

Include, as applicable: affected endpoint/file, reproduction steps, impact, suggested fix. Our commitment: acknowledgment within 24h, initial severity assessment within 72h, patch or mitigation plan within 14 days. Reporters who wish to be credited are listed in the Hall of Fame below.

---

## Threat model (what we defend against today)

Universal Document OS is designed for **localhost / trusted-network deployment**. The security controls below assume an attacker who can send HTTP requests to the service; they do **not** yet assume a multi-tenant public deployment (that requires auth — see "Known gaps").

### Implemented defenses (with source references)

| Risk | Control | Where | Test coverage |
|---|---|---|---|
| Path traversal via download names (`../../etc/passwd`) | `resolve_within()` resolves symlinks and enforces containment inside `data/outputs/`; escapes return plain `404` | `app/security.py` | `tests/test_security.py` (live attack attempts incl. subdirectory tricks & symlink escape) |
| Filename injection on upload (paths, `..`, hidden files like `.env`, shell metacharacters) | `sanitize_filename()`: basename-only, traversal collapsed, leading dot/dash stripped, charset allowlist, Persian preserved, ≤180 chars | `app/security.py` | `tests/test_security.py` |
| Disk exhaustion via huge uploads | Streamed writes with hard byte ceiling `MAX_UPLOAD_BYTES` (default 25 MB); partial file deleted, clean `413` | `app/main.py`, `app/config.py` | `tests/test_security.py` |
| Arbitrary file read through workroom naming | Job ids are server-generated UUIDs; user filename never forms a path component alone | `app/main.py` | pipeline tests |
| Crash-of-the-day via malformed documents | Extraction errors become tagged strings (`[EXTRACTION_ERROR]`), never 5xx; audit write failure cannot break requests | `app/main.py`, `app/adapters` | `tests/test_extract.py` |
| Secrets leakage | Zero hardcoded secrets; all credentials env-driven; `.env.example` contains placeholders only; CI secret scan | repo-wide | CI |
| Container escape / privilege abuse | Multi-stage Dockerfile, non-root `appuser` (uid 1001), minimal runner, data dirs chowned at build | `Dockerfile` | manual drill |
| Information disclosure in errors | Download failures deliberately indistinguishable (uniform 404) | `app/main.py` | security tests |

### Operational hardening you should do

1. **Keep it off the public internet** until authentication ships. Bind to `127.0.0.1` or put it behind your reverse proxy with network policy.
2. `chmod 600 .env` (the installer already does this). Never commit `.env`.
3. Generate strong provider keys: `openssl rand -base64 32`. Rotate SMS/Telegram tokens if leaked.
4. Treat `data/audit.jsonl` as sensitive: it records filenames and sizes. Restrict filesystem permissions on `data/`.
5. Backups (`backup.sh`) contain `.env` — store them encrypted (`openssl enc -aes-256-cbc`) and off-machine.
6. Update regularly (`./update.sh`); pre-3.2 releases lack the traversal/sanitization fixes.

---

## Known gaps (stated plainly)

These are honest limitations of v3.2.4, each tracked in [ROADMAP.md](ROADMAP.md):

1. **No authentication/authorization** — anyone reaching the port can upload and list status counters. Do not deploy publicly.
2. **No rate limiting** — a local/network peer can flood jobs (disk grows until quota tooling lands).
3. **No TLS termination** — run behind HTTPS-capable proxy if traffic leaves the machine.
4. **Content scanning absent** — uploaded files are stored, not virus-scanned; don't process untrusted third-party documents on a shared workstation.
5. **Notification channels** — Telegram/SMS providers send real messages when enabled; misconfigured `TELEGRAM_CHAT_ID` could leak job info to the wrong chat. Verify config after changes.

If any of these blocks your use case, open a GitHub issue to prioritize it — that's product risk, not a vulnerability report.

---

## Hall of Fame

*No public disclosures yet.* First valid report gets a line here (with your permission).

---

## خلاصه فارسی

- **گزارش آسیب‌پذیری فقط خصوصی:** GitHub Advisory یا ایمیل `security@ansariaiadmin.dev` — تایید ۲۴ ساعته، بررسی ۷۲ ساعته، فیکس تا ۱۴ روز.
- **دفاعهای پیاده‌شده:** ضد Path Traversal در دانلود (با resolve کامل + symlink)، sanitize نام فایل آپلود، سقف حجم آپلود (۴۱۳ تمیز)، صفر راز در کد، داکر non-root، لاگ ممیزی append-only.
- **کارهایی که شما باید بکنید:** فعلاً اپ را عمومی نکنید (احراز هویت هنوز نیامده)؛ `.env` با مجوز ۶۰۰؛ کلیدها را تصادفی قوی بسازید؛ بکاپ را رمزنگاری کنید؛ مرتب `./update.sh` بزنید.
- **محدودیت‌های صادقانه:** بدون Auth، بدون Rate-Limit، بدون TLS داخلی، بدون آنتی‌ویروس روی آپلود — همه در ROADMAP ثبت شده‌اند.
