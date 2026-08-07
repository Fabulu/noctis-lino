# Wave 9 — audio + polish

## Audio verdict: SILENCE. Port nothing.

Verified exhaustively (Wave 9 recon, 2026-08-07):
- The 7 .VOC files are Noctis-II leftovers — the author's own build note says "there for curiosity."
- Zero source references to any VOC filename in either tree.
- Zero `.voc` strings in any of the 16 shipped binaries.
- No PC-speaker code, no MIDI device, no sound-card I/O.
- The niv-lr maintainer themselves wrote "atmospheric noises NOTE: Where?!?!" — they couldn't find the hook either.

**The port has ZERO fidelity obligation for audio. Silence is the faithful ship state.**
The WAVEPLAN §9 mixer/VOC deliverables are empty — superseded by PORTPLAN's "MIDI: SETTLED."

## Wave 9 scope: QA + polish

1. **Regression consolidation** — full `run_all.py` green after all waves' deltas. **BLOCKED by F1** (test_ground.py unregistered — coordinator's action).
2. **Performance soak** — integrated multi-hour tick under exclusive mode. Component probes pass (0.799ms clear+palette, 55.0000ms median tick); the integrated soak is what Wave 9 owes.
3. **PLAYTEST.md checklist** — author + execute the launch → target → fly → land → walk → name → save loop.
4. **Polish backlog** — any remaining items from earlier waves.

## Open items from earlier waves (carry or close)

| # | Item | Wave 9 action |
|---|---|---|
| 1 | create_sky byte-exactness (7b sub-wave) | Close (biggest visible loose end) or carry documented flag |
| 2 | Type-3 seed-flow gap (7b) | Resolve (brtl dump) or carry XFAIL |
| 3 | Wave 8 ip_reached follow-up | Investigate second flag source |
| 4 | nsrun NSIN validation (OPENITEMS #4) | Apply 2-line fix |
| 5 | pg_ref alfa≠0 (6a) | RESOLVED — oracle was wrong, port correct |
| 6 | w5audit budget (4 voids) + fb_compare suite FAIL | Optional harness cleanup |
| 7 | Planetary geometry ungraded vs 1996 | Can't close — no oracle; restate bound |
| 8 | genfp bare-fistp rule | Post-port; not Wave 9 |
| 9 | Doc typos (FLOATSITES label, GUIDE.BIN precondition) | Trivial |
