@echo off
chcp 65001 >nul
title Pannello Paola  -  TIENI APERTA QUESTA FINESTRA
cd /d "%~dp0"

echo.
echo   Avvio del pannello in corso...
echo   Si aprira' da solo nel browser tra qualche secondo.
echo.
echo   NON chiudere questa finestra mentre lavori.
echo   Quando hai finito, chiudila pure.
echo.

where py >nul 2>nul && (py admin.py) || (python admin.py)

echo.
echo   Il pannello e' stato chiuso. Puoi chiudere questa finestra.
pause >nul
