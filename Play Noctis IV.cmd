@echo off
setlocal

rem Noctis IV uses relative paths for its assets, save, catalogue, and logs.
rem Anchor them to this relocatable bundle even when Explorer or another
rem launcher supplies a different working directory.
pushd "%~dp0" || exit /b 2
"%~dp0Noctis-IV.exe"
set "noctis_exit=%errorlevel%"
popd
exit /b %noctis_exit%
