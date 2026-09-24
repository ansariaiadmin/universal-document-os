# Universal Document OS — Local App + Landing

## سریع‌ترین اجرا
Linux/macOS:
```bash
./run.sh
```
Windows:
```bat
run.bat
```

سپس:
- Landing: http://localhost:8000/
- Panel: http://localhost:8000/app
- Health: http://localhost:8000/api/health

## Docker
```bash
docker compose up --build
```

## این نسخه واقعاً چه کار می‌کند؟
- Landing page آماده
- پنل محلی آماده
- Upload واقعی فایل
- تشخیص فرمت
- Workroom برای هر Job
- استخراج واقعی متن از PDF/DOCX/XLSX/TXT/MD/CSV/HTML/JSON/RTF
- تولید خروجی واقعی TXT/MD برای محتوای متنی
- Audit log
- API health/status
- Docker
- ساختار آماده توسعه برای Leader/Society/Quality Gate

## اتصال به URL
روی سرور:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
سپس Reverse Proxy مثل Nginx/Caddy را روی دامنه قرار دهید و HTTPS فعال کنید.

## نکته مهم
این build یک محصول MVP اجرایی است، نه ادعای پشتیبانی کامل از همه فرمت‌ها و «۱۰/۱۰ جهانی».
برای نسخه Production باید Adapterهای کامل فرمت‌ها، OCR چندموتوره، ترجمه، بازسازی layout،
Golden Benchmark واقعی برای هر Society، Evaluatorهای مستقل، Release Manager و
Leader Governance به‌صورت واقعی تکمیل و Benchmark شوند.
