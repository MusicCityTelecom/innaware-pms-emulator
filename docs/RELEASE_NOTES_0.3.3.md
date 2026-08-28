# InnAware PMS Emulator 0.3.3 - Development Release Notes

## Fixed

- Protocol-pack update detection now compares the pack version encoded in the
  published asset name before considering the archive digest.
- Rebuilding the same pack version no longer creates a false update merely
  because ZIP timestamps changed the archive SHA-256.
- The remote pack version is included explicitly in update status details.

This completes the Update Center correction started in 0.3.2.
