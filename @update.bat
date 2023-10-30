@echo off
@REM
@REM Name: DWG POS - Updater
@REM Purpose: To update the POS system to the latest version
@REM Written: 7/8/2023
@REM Author: Trent Buckley
@REM
@REM
@REM Abstract:
@REM     When the program is run, it will connect to the NAS on U:/ and copy the latest version of the program to the
@REM     computer. It will then run the program and close itself.
@REM
@REM
@REM Change Log:
@REM     v0 -- 28/7/2023 - Initial Commit

@REM Set the variables
set "source=U:\POS\dist\POS\*"
set "destination=%userprofile%\POS\*"

@REM Kill the program if it is running
taskkill /IM POS.exe /F

@REM Copy the files
xcopy /s /y "%source%" "%destination%"

@REM Inform the user that the program has been updated
echo The program has been updated.
timeout /t 5

@REM Run the program
start "" "%userprofile%\POS\POS.exe"

@REM Close this program
exit
