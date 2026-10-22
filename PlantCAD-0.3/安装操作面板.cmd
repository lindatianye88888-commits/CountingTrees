@echo off
title CountingTrees - ÊýÊ÷
where py >nul 2>nul
if errorlevel 1 (
  python "%~dp0install_panel.py"
) else (
  py -3 "%~dp0install_panel.py"
)
pause
