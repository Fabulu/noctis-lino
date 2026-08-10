# PLAYTEST.md - Noctis-IV -> L.in.oleum port test checklist

This is a test checklist and capability inventory; no interactive playtest is
claimed as executed here.

## Final verified automated status (2026-08-08)

- Sky suite: `tests/test_sky.py` **16/16 PASS** in 1999 s.
- Canonical Python/C/Lino: **27/27 cases, 408 records**; first launch exact.
- Malformed-input checks: **7/7**.
- Binary anchors: exact.
- C mutants: **26/26**; static and dynamic Lino mutants: **27/27**.
- H1 source/work immutability: PASS.
- Replay SHA-256: `a68a5775f2ad05d04cdd6c399b42f06a5d2a24cd555e81348ef7e47f70ecf421`.

Screenshots are ungraded. The type-3 `p_surfacemap` `round_hill` mismatch remains
a measured **XFAIL (39,710 bytes)**.

The 27-case/26C+27Lino mutation run is historical closeout evidence, not the routine bar.
For delivery, use one focused smoke/regression check for the changed behavior. Screenshots
and this checklist are product feedback; they should not expand into another oracle or a
mandatory adversarial-testing process. A deeper `--deep` audit is optional for high-risk
oracle changes.

## Interactive checklist

The following remain an interactive checklist, not an execution claim:

- launch
- target
- fly
- land
- walk
- name
- save

The bounded integrated soak is automated separately; multi-hour stability and a
live interactive launch/target/fly/land/walk/name/save playtest remain unverified.
