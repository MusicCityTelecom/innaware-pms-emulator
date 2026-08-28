# InnAware PMS Emulator 0.3.2 - Development Release Notes

## Fixed

- The Update Center now treats GitHub's `sha256:<digest>` asset value and the
  installed protocol pack's bare SHA-256 value as equivalent.
- An already-installed current protocol pack is labeled **Current / none** and
  its install button remains disabled instead of repeatedly reinstalling the
  same pack.

The protocol pack itself was installing correctly in 0.3.1; this release fixes
the stale update indicator and comparison logic.
