@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Forex Hybrid Trading System

echo ============================================================
echo    Forex Hybrid Trading System - Launcher
echo ============================================================
echo.

rem --- check Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3 was not found on this computer.
    echo.
    echo Install it from https://www.python.org/downloads/
    echo and tick "Add python.exe to PATH" during setup.
    echo.
    pause
    exit /b 1
)

rem --- install packages on first run only ---
python -c "import numpy, pandas, yfinance, sklearn, requests, matplotlib" >nul 2>&1
if errorlevel 1 (
    echo First run: installing required packages...
    echo This happens once and needs an internet connection.
    echo.
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Package install failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
    echo.
    echo Packages installed successfully.
)

:menu
echo.
echo ============================================================
echo   Choose an option and press Enter:
echo.
echo   1. BACKTEST: mean reversion (best strategy)
echo   2. BACKTEST: Donchian + ML (full run)
echo   3. BACKTEST: quick (EURUSD only)
echo   4. BACKTEST: EMA crossover
echo   5. BACKTEST: custom capital and risk
echo   6. PAPER TRADE: live on practice (one check)
echo   7. PAPER TRADE: dry-run (no orders placed)
echo   8. Open the results folder
echo   9. Exit
echo ============================================================
set "choice="
set /p "choice=Your choice (1-9): "

if "%choice%"=="1" goto run_mr
if "%choice%"=="2" goto run_full
if "%choice%"=="3" goto run_quick
if "%choice%"=="4" goto run_ema
if "%choice%"=="5" goto run_custom
if "%choice%"=="6" goto run_paper
if "%choice%"=="7" goto run_paper_dry
if "%choice%"=="8" goto open_reports
if "%choice%"=="9" goto end

echo Invalid choice. Please type a number from 1 to 9.
pause
goto menu

:run_mr
echo.
echo Running mean reversion backtest (daily)...
echo.
python main.py --strategy meanreversion --pairs EURGBP=X AUDUSD=X EURUSD=X GBPUSD=X
goto after_run

:run_full
echo.
echo Running full Donchian + ML backtest (30-60 seconds)...
echo.
python main.py
goto after_run

:run_quick
echo.
echo Running quick backtest on EURUSD...
echo.
python main.py --pairs EURUSD=X
goto after_run

:run_ema
echo.
echo Running EMA crossover strategy...
echo.
python main.py --strategy ema
goto after_run

:run_custom
echo.
set /p "cap=Starting capital (e.g. 100000): "
set /p "riskpct=Risk per trade in percent (e.g. 1): "
if "%cap%"=="" set "cap=100000"
if "%riskpct%"=="" set "riskpct=1"
echo.
echo Running with capital %cap% and risk %riskpct% percent...
echo.
python main.py --capital %cap% --risk-pct %riskpct%
goto after_run

:run_paper
echo.
echo Running paper trade on your OANDA PRACTICE account (one check)...
echo.
python paper_trade.py
goto after_run

:run_paper_dry
echo.
echo Paper trade DRY RUN - shows what it WOULD do, places no orders...
echo.
python paper_trade.py --dry-run
goto after_run

:after_run
echo.
echo Opening the results folder...
start "" "%~dp0reports"
echo.
echo Done. See the charts (PNG) and summary.txt in the reports folder.
echo.
pause
goto menu

:open_reports
start "" "%~dp0reports"
pause
goto menu

:end
echo.
echo Goodbye.
endlocal
exit /b 0