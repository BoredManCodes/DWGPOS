"""
Abstract:
    This file is used to update the DWGPOS system.
    It will check the version of the DWGPOS system and update it if necessary.
    It will install itself as a system service and run in the background.
    It will check the version of the DWGPOS system every 5 minutes.
    It will download the latest version of the DWGPOS system from the server.
    It will install the latest version of the DWGPOS system.
    It will restart the DWGPOS system.
    It will send a notification to the server when the update is complete.
    pyisntaller one file: pyinstaller --onefile --noconsole --icon=icon.ico updater.py
"""
import os
import sys
import shutil
import requests

# Global variables
# The path of the DWGPOS system.
DWGPOS_SERVER_PATH = r'\\192.168.20.230\MasterFileStorage\POS\dist\POS'
DWGPOS_UPDATER_PATH = r'\\192.168.20.230\MasterFileStorage\POS\DWGPOSUpdater.exe'
DWGPOS_CLIENT_PATH = r'%userprofile%\POS\\'
COMPUTER_NAME = os.environ['COMPUTERNAME']

# Check if the updater is already installed as a system service, if not install it and start it. Then exit.
if not os.path.exists(os.path.join(os.environ['WINDIR'], 'System32', 'DWGPOSUpdater.exe')):
    # Install the updater as a system service.
    # copy the updater from the server to the client.
    shutil.copyfile(DWGPOS_UPDATER_PATH, os.path.join(os.environ['WINDIR'], 'System32', 'DWGPOSUpdater.exe'))
    # Create a registry key to run the updater as a system service.
    os.system('reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run" /v "DWGPOSUpdater" /t REG_SZ /d "%WINDIR%\System32\DWGPOSUpdater.exe" /f')
    # Start the updater.
    os.system('start %s' % os.path.join(os.environ['WINDIR'], 'System32', 'DWGPOSUpdater.exe'))
    # Exit the current updater.
    sys.exit()

# Check the version from the current DWGPOS executable's metadata.
CURRENT_VERSION = os.popen("powershell -NoLogo -NoProfile -Command '(Get-Item -Path 'U:\POS\dist\POS\POS.exe').VersionInfo'"')
# Check the version from the latest DWGPOS executable's metadata.
LATEST_VERSION = os.popen('wmic datafile where name="%s" get Version' % os.path.join(DWGPOS_SERVER_PATH, 'POS.exe')).read().split('\n')[1].strip()
print(CURRENT_VERSION, LATEST_VERSION)
# if CURRENT_VERSION != LATEST_VERSION:
#     # Kill the current DWGPOS system.
#     os.system('taskkill /IM POS.exe /F')
#     # Copy all the files from the server to the client.
#     shutil.copytree(DWGPOS_SERVER_PATH, DWGPOS_CLIENT_PATH)
#     # Start the DWGPOS system.
#     os.system('start %s' % os.path.join(DWGPOS_CLIENT_PATH, 'POS.exe'))
#     # Send a notification to the server.
#     requests.post('https://discord.com/api/webhooks/1163346529759789057/Q93pKZGdCtbJ_vxKzpLCUzYZZIEtFGSdZPXeJSq2soq9dYejztv8-IVNXrXyvU3g6aCd', data={'content': f'DWGPOS system has been updated to version {LATEST_VERSION} on {COMPUTER_NAME}'})

