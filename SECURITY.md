# Security Policy — Universal Document OS

**Applies to:** v4.2.0 and later · **Language of this doc:** English (Persian summary at the end)

---

## Supported versions

| Version | Supported | Notes |
|---|---|---|
| 4.2.x | ✅ | Current baseline: content guard, opt-in auth (timing-safe), opt-in rate limiting |
| < 4.2 | ❌ | Upgrade before reporting issues against them |

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
| Path traversal via download names (`../../etc/passwd`) | `resolve_within()` resolves symlinks and enforces containment inside `data/outputs/`; escapes return plain `404` | `app/security.py` | `tests/test_security.py` |
| Filename injection on upload (paths, `..`, hidden files like `.env`, shell metacharacters) | `sanitize_filename()`: basename-only, traversal collapsed, leading dot/dash stripped, charset allowlist, Persian preserved, ≤180 chars | `app/security.py` | `tests/test_security.py` |
| Disk exhaustion via huge uploads | Streamed writes with hard byte ceiling `MAX_UPLOAD_BYTES` (default 25 MB); partial file deleted, clean `413` | `app/main.py`, `app/config.py` | `tests/test_security.py` |
| Executable disguised as document (`evil.exe` renamed `report.pdf`) | Content guard: MZ/ELF/shebang magic bytes hard-rejected with `415` before extraction | `app/content_guard.py` | `tests/test_v41_adaptive.py` |
| Zip bombs (OOXML/ODF containers) | Declared-size check + actual streaming decompression budget + compression-ratio guard → `415` | `app/content_guard.py` | `tests/test_v41_adaptive.py` |
| Memory blow-up from a legal-but-huge document | Extraction bounded by `MAX_EXTRACT_BYTES`/`MAX_TEXT_CHARS` (truncation, never OOM) | `app/adapters/__init__.py` | `tests/test_v41_adaptive.py` |
| API abuse when exposed to a network | Opt-in `X-API-Key` middleware (timing-safe comparison) + opt-in sliding-window rate limit → `401`/`429` | `app/auth.py`, `app/ratelimit.py` | `tests/test_enterprise.py`, `tests/test_v43.py` |
| Crash-of-the-day via malformed documents | Extraction errors become tagged strings, never 5xx; audit write failure cannot break requests | `app/main.py`, `app/adapters` | `tests/test_extract.py` |
| Secrets leakage | Zero hardcoded secrets; all credentials env-driven; `.env.example` contains placeholders only; `.env` never copied into backups (redacted snapshot) | repo-wide | `backup.sh` behavior |
| Private documents baked into images | `.dockerignore` excludes `data/`, `backups/`, `.env`, `.git` from the build context | `.dockerignore` | build-time |
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

These are honest limitations of v4.2.0, each tracked in [ROADMAP.md](ROADMAP.md):

1. **Auth is opt-in, not default** — unless `UDO_API_KEYS` is set, anyone reaching the port can upload and read counters. Enable it before any shared-network deployment.
2. **Rate limiting is opt-in** — set `RATE_LIMIT_PER_MIN`; it is per-process, so behind multiple workers scale the number accordingly.
3. **No TLS termination** — run behind an HTTPS-capable proxy if traffic leaves the machine.
4. **Content scanning absent** — uploaded files are stored, not virus-scanned; don't process untrusted third-party documents on a shared workstation.
5. **Notification channels** — Telegram/SMS providers send real messages when enabled; misconfigured `TELEGRAM_CHAT_ID` could leak job info to the wrong chat. Verify config after changes.

If any of these blocks your use case, open a GitHub issue to prioritize it — that's product risk, not a vulnerability report.

---

## Hall of Fame

*No public disclosures yet.* First valid report gets a line here (with your permission).

---

## خلاصه فارسی

- **گزارش آسیب‌پذیری فقط خصوصی:** GitHub Advisory یا ایمیل `security@ansariaiadmin.dev` — تایید ۲۴ ساعته، بررسی ۷۲ ساعته، فیکس تا ۱۴ روز.
- **دفاعهای پیاده‌شده:** ضد Path Traversal در دانلود، sanitize نام فایل، سقف حجم آپلود (۴۱۳)، گارد magic bytes و zip-bomb (۴۱۵)، بودجه‌ی استخراج حافظه، auth اختیاری با مقایسه‌ی امن، rate limit اختیاری، صفر راز در کد، داکر non-root و بدون data/ در ایمیج، لاگ ممیزی append-only.
- **کارهایی که شما باید بکنید:** روی شبکه‌ی غیرمطمئن `UDO_API_KEYS` را ست کنید؛ `.env` با مجوز ۶۰۰؛ کلیدها را تصادفی قوی بسازید؛ نسخه‌ی اصلی `.env` را جداگانه رمزنگاری‌شده نگه دارید؛ مرتب `./update.sh` بزنید.
- **محدودیت‌های صادقانه:** auth و rate limit پیش‌فرض خاموش‌اند (اختیاری‌اند)، بدون TLS داخلی، بدون آنتی‌ویروس روی آپلود — همه در ROADMAP ثبت شده‌اند.
