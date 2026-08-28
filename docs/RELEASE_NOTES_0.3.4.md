# InnAware PMS Emulator 0.3.4 - Development Release Notes

## Voiceware / OperaIP correction

- The saved `OPERAIP_FIAS` compatibility ID now emits the fixed legacy commands
  advertised by Voiceware (`CHK`, `NAM`, `MOV`, `WKP`, and related masks).
- It retains the field-observed ENQ/ACK and STX/ETX transport behavior.
- It no longer sends a FIAS `GI|...` record to a Voiceware interface configured
  for the legacy command masks.

## Optional property laboratory

- Front Desk / Guest Operations can now send directly through a selected PMS
  interface when no property is selected.
- Direct check-in, checkout, move, wakeup set, and wakeup cancel operations do
  not create or require property, room, guest, or stay records.
- Selecting a property continues to use the existing stateful property lab.
