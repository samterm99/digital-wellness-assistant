@echo off
rem Records how Windows classifies your current activity for 90 seconds -> logs\diag.txt
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
echo กำลังบันทึก 90 วินาที ระหว่างนี้ลองเปิด YouTube / Netflix เต็มจอ แล้วออกจากเต็มจอ
python -m wellness --diag
echo เสร็จแล้ว ผลอยู่ที่ logs\diag.txt
type logs\diag.txt
pause
