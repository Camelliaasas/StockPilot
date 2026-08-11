@echo off
REM StockPilot 一键启动
cd /d %~dp0
echo ========================================
echo   StockPilot - AI 股票分析助手
echo ========================================

REM 检查 Python
where python >nul 2>nul
if %errorlevel%==0 (
    set PY=python
) else (
    echo [错误] 未找到 Python，请安装 Python 3.11+
    pause
    exit /b 1
)

REM 检查依赖
%PY% -c "import flask, akshare" >nul 2>nul
if not %errorlevel%==0 (
    echo [首次运行] 安装依赖...
    %PY% -m pip install -r requirements.txt
)

REM 启动看板
echo [启动] 看板服务 http://127.0.0.1:5521
start http://127.0.0.1:5521
%PY% webui.py
