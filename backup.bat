@echo off
echo Backup: Universal Document OS
echo ========================================
if not exist data (
  echo No data directory - nothing to back up
  pause
  exit /b 1
)
if not exist backups mkdir backups
set TS=%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%
set TS=%TS: =0%
tar -czf backups\udo-backup-%TS%.tar.gz data
if %errorlevel%==0 (echo Backup done: backups\udo-backup-%TS%.tar.gz) else (echo Backup failed)
echo Note: .env itself is not copied - keep your own encrypted copy of it.
pause
