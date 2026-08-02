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
  REM  --autostash: se Paola ha foto caricate ma non ancora pubblicate, la
  REM  cartella e' "sporca" e un pull normale si RIFIUTA di partire. Con
  REM  --autostash il lavoro in corso viene messo da parte e rimesso a posto
  REM  da solo appena finito l'aggiornamento.
  REM  L'esito finisce in un file e viene mostrato DOPO il "cls" qui sotto:
  REM  scrivendolo qui verrebbe cancellato dallo schermo prima che lei possa
  REM  leggerlo, ed e' cosi' che questo PC e' rimasto due mesi indietro senza
  REM  che nessuno se ne accorgesse.
  git pull --autostash --no-rebase --no-edit > "%TEMP%\pannello-pull.txt" 2>&1
  if errorlevel 1 set "PULL_FALLITO=1"
  set "GIT_PRESENTE=1"
)

REM  Controllo separato e indispensabile: quando l'autostash non riesce a
REM  rimettere a posto il lavoro di Paola, git esce con SUCCESSO (esito 0) ma
REM  lascia i marcatori di conflitto dentro i file. data/series.json
REM  diventerebbe JSON non valido e il pannello lavorerebbe sul catalogo rotto.
REM  "git ls-files -u" e' l'unico modo per accorgersene.
del "%TEMP%\pannello-conflitti.txt" >nul 2>nul
if defined GIT_PRESENTE git ls-files -u > "%TEMP%\pannello-conflitti.txt" 2>nul
if exist "%TEMP%\pannello-conflitti.txt" for %%A in ("%TEMP%\pannello-conflitti.txt") do if %%~zA GTR 0 set "PULL_CONFLITTO=1"

REM  Prima di arrendersi, un tentativo: quasi sempre non c'e' nessun vero
REM  disaccordo (Andrea ha ritoccato i testi delle serie, Paola ha aggiunto
REM  opere) e il pannello sa unire le due versioni da solo. Se ci riesce si
REM  prosegue normalmente; il blocco qui sotto resta per i casi veri.
REM  Nessun "echo" qui: siamo prima del "cls" e verrebbe cancellato.
if defined PULL_CONFLITTO (
  %PY% admin.py --ripara-conflitto > "%TEMP%\pannello-riparazione.txt" 2>&1
  if not errorlevel 1 (
    set "PULL_CONFLITTO="
    set "RIPARATO=1"
  )
)

cls
echo.
echo   ====================================================
echo      PANNELLO PAOLA
echo   ====================================================
echo.

REM  Gli avvisi vanno stampati QUI, dopo il "cls": scritti prima verrebbero
REM  cancellati dallo schermo senza che Paola faccia in tempo a leggerli.

REM  Conflitto rientrato da solo: si parte, ma Paola deve sapere cos'e'
REM  successo, altrimenti non si spiega perche' il catalogo e' cambiato.
if defined RIPARATO (
  echo   ----------------------------------------------------
  echo   Nota: c'era una modifica arrivata da Andrea che si
  echo   sovrapponeva al tuo lavoro. Le ho unite da sola:
  echo   non hai perso niente e puoi lavorare tranquilla.
  echo.
  echo   Ricordati di premere "Pubblica sul sito" quando hai
  echo   finito, cosi' le modifiche vanno online.
  echo   ----------------------------------------------------
  echo.
)

REM  Conflitto vero: il pannello NON deve partire. Lavorare su un catalogo a
REM  meta' rischia di rovinare i dati delle opere, ed e' un danno peggiore di
REM  un'attesa.
if defined PULL_CONFLITTO (
  echo   ----------------------------------------------------
  echo   MI FERMO QUI: c'e' una modifica in conflitto.
  echo.
  echo   Il tuo lavoro NON e' perso, e' al sicuro. Ma il file
  echo   del catalogo e' rimasto a meta' e il pannello non
  echo   deve partire in queste condizioni.
  echo.
  echo   Ho gia' provato a sistemarlo da sola senza riuscirci,
  echo   quindi serve una mano.
  echo.
  echo   Chiama Andrea e fagli vedere questa finestra.
  echo   ----------------------------------------------------
  echo.
  echo   ^(per Andrea: dettaglio del tentativo in
  echo    %TEMP%\pannello-riparazione.txt^)
  echo.
  pause
  exit /b 1
)

if defined PULL_FALLITO (
  echo   ----------------------------------------------------
  echo   NON sono riuscito a scaricare gli aggiornamenti.
  echo   Puoi lavorare lo stesso, ma il pannello potrebbe
  echo   essere una versione vecchia. Dettaglio del problema:
  echo.
  type "%TEMP%\pannello-pull.txt"
  echo.
  echo   Se questo messaggio si ripete, fai una foto della
  echo   finestra e mandala ad Andrea.
  echo   ----------------------------------------------------
  echo.
  pause
  echo.
)

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
