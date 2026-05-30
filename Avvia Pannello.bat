@echo off
chcp 65001 >nul
title Pannello Paola  -  TIENI APERTA QUESTA FINESTRA
cd /d "%~dp0"

echo.
echo   Controllo iniziale in corso, attendi qualche secondo...

REM Assicura che le librerie necessarie siano installate (solo se mancano)
py -c "import PIL, cgi" 2>nul || py -m pip install --quiet Pillow legacy-cgi

cls
echo.
echo   ====================================================
echo      PANNELLO PAOLA
echo   ====================================================
echo.
echo   Il pannello si aprira' da solo nel browser.
echo.
echo   - NON chiudere questa finestra mentre lavori
echo   - Quando hai finito, chiudila pure
echo.
echo   Se il browser non si apre da solo, scrivi nella
echo   barra dell'indirizzo:  localhost:8765
echo.

py admin.py

echo.
echo   Pannello chiuso. Puoi chiudere questa finestra.
pause >nul
