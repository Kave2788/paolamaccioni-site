@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Pannello Paola  -  TIENI APERTA QUESTA FINESTRA
cd /d "%~dp0"

cls
echo.
echo   ====================================================
echo      PANNELLO PAOLA
echo   ====================================================
echo.
echo   Controllo iniziale, attendi qualche secondo...
echo.

REM --- 1. Trova Python -----------------------------------------------------
REM  "py" e' il lanciatore ufficiale di Windows; "python" e' la riserva.
set "PY="
py -c "import sys" >nul 2>nul && set "PY=py"
if not defined PY (
  python -c "import sys" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo   PROBLEMA: Python non risulta installato su questo computer.
  echo.
  echo   Il pannello non puo' partire senza. Avvisa Andrea:
  echo   serve installare Python da python.org spuntando
  echo   "Add Python to PATH".
  echo.
  pause
  exit /b 1
)

REM --- 2. Libreria per le foto ---------------------------------------------
%PY% -c "import PIL" >nul 2>nul
if errorlevel 1 (
  echo   Installo il componente per le foto, un momento...
  %PY% -m pip install --quiet --disable-pip-version-check Pillow >nul 2>nul
  %PY% -c "import PIL" >nul 2>nul
  if errorlevel 1 (
    echo.
    echo   PROBLEMA: manca un componente e non riesco a scaricarlo.
    echo   Controlla che il computer sia connesso a internet e riprova.
    echo   Se il problema resta, avvisa Andrea.
    echo.
    pause
    exit /b 1
  )
)

REM --- 3. Aggiornamenti del sito -------------------------------------------
REM  Scarica le eventuali modifiche fatte da Andrea. Se non c'e' rete o il
REM  comando fallisce si prosegue lo stesso: il pannello funziona comunque.
where git >nul 2>nul
if errorlevel 1 (
  echo   Nota: git non e' installato, il tasto "Pubblica" non funzionera'.
  echo   Puoi caricare le foto lo stesso. Avvisa Andrea.
  echo.
) else (
  git pull --no-rebase --no-edit >nul 2>nul
  if errorlevel 1 (
    echo   Nota: non sono riuscito a scaricare gli aggiornamenti
    echo   ^(succede se manca internet^). Si prosegue comunque.
    echo.
  )
)

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

%PY% admin.py
set "ESITO=%ERRORLEVEL%"

echo.
if not "%ESITO%"=="0" (
  echo   ----------------------------------------------------
  echo   Il pannello si e' chiuso per un problema.
  echo   Le foto gia' caricate NON sono perse: restano
  echo   salvate sul computer.
  echo   Fai una foto a questa finestra e mandala ad Andrea.
  echo   ----------------------------------------------------
) else (
  echo   Pannello chiuso.
)
echo.
echo   Premi un tasto qualsiasi per chiudere questa finestra.
pause >nul
