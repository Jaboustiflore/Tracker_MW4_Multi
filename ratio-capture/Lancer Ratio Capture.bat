@echo off
setlocal
cd /d "%~dp0"
title Ratio Capture

if exist ".venv\Scripts\pythonw.exe" goto lancer

echo.
echo  === Ratio Capture : premiere installation ===
echo.

set "PY="
for %%V in (3.12 3.13 3.11) do (
  if not defined PY (
    py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V"
  )
)
if not defined PY (
  python -c "import sys; assert (3,9) <= sys.version_info[:2] <= (3,13)" >nul 2>nul && set "PY=python"
)
if not defined PY goto installer_python

echo  Python trouve : %PY%
echo  Creation de l'environnement (1 a 3 minutes)...
%PY% -m venv .venv || goto erreur
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
".venv\Scripts\python.exe" -m pip install numpy opencv-python mss --quiet || goto erreur
echo  Ajout de la capture DirectX (facultatif)...
".venv\Scripts\python.exe" -m pip install dxcam --quiet || echo  (dxcam non installe : la capture standard sera utilisee)
echo  Installation terminee.

:lancer
start "" ".venv\Scripts\pythonw.exe" "%~dp0ratio_capture.py"
exit /b 0

:installer_python
echo  Python 3.12 n'est pas installe sur ce PC.
echo  Il est necessaire pour faire tourner Ratio Capture (gratuit, officiel).
echo.
choice /c ON /m " L'installer maintenant avec winget (O = oui, N = non)"
if errorlevel 2 goto sans_python
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
echo.
echo  Python est installe. Ferme cette fenetre et relance "Lancer Ratio Capture.bat".
pause
exit /b 0

:sans_python
echo.
echo  Installe Python 3.12 depuis https://www.python.org/downloads/release/python-3128/
echo  (coche "Add python.exe to PATH"), puis relance ce fichier.
pause
exit /b 1

:erreur
echo.
echo  L'installation a echoue. Fais une capture de cette fenetre et envoie-la a Claude.
pause
exit /b 1
