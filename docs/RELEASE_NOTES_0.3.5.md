# InnAware PMS Emulator 0.3.5 - Development Release Notes

## Windows upgrade fix

- The installer now force-closes only the `InnAware-PMS-Emulator.exe` process
  tree before replacing the installed executable.
- This handles PyInstaller one-file launcher/child processes that Windows
  Restart Manager did not consistently close.
- Upgrades no longer require manually deleting files or running Setup as
  administrator.
- The installer does not automatically relaunch applications during its file
  replacement phase.

## Protocol clarity

- Generic FIAS is labeled explicitly as CRLF and no ENQ/ACK.
- Its description warns that the PBX must be configured for the same transport.
- Voiceware interfaces advertising `AREYUTHERE/CHK/NAM/MOV/WKP` should use the
  OperaIP compatibility profile rather than Generic FIAS.
