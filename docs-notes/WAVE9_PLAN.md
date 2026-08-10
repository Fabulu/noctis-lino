# Wave 9 - audio + polish

## Audio verdict: SILENCE. Port nothing.

Verified exhaustively (Wave 9 recon, 2026-08-07): the seven VOC files are Noctis-II leftovers, with no source or binary references. There is no PC-speaker, MIDI, or sound-card I/O. Silence is the faithful ship state; the audio deliverables are superseded by PORTPLAN's MIDI decision.

## Wave 9 scope: QA + polish

### Final sky closeout (2026-08-08)

`tests/test_sky.py` is **16/16 PASS** in 1999 s. Canonical Python/C/Lino agree
on **27/27 cases and 408 records**; first launch is exact, malformed-input
coverage is **7/7**, binary anchors are exact, C mutants are **26/26**, static
and dynamic Lino mutants are **27/27**, and H1 source/work immutability passes.
Replay SHA-256:
`a68a5775f2ad05d04cdd6c399b42f06a5d2a24cd555e81348ef7e47f70ecf421`.
Screenshots are ungraded. The type-3 `p_surfacemap` `round_hill` mismatch remains
a measured **XFAIL (39,710 bytes)**.

The long 27-case/26C+27Lino run above is retained as one-time historical evidence. Wave 9
uses a delivery-first default: one focused smoke/regression check for changed behavior. An
optional `--deep` run is reserved for high-risk oracle changes; full-suite, recursive
adversarial review, and mutation work are not permanent acceptance requirements. Screenshots
and interactive playtest are product feedback rather than oracle construction.

1. **Regression consolidation** - `test_ground.py` is registered; the current inventory is 22 registered tests and 0 unregistered. `nsrun` NSIN validation is fixed and `test_geometry` passes.
2. **Performance soak** - bounded integrated tick is now covered by `tests/soak_game.py`. It copies `work/game.txt` plus its declared libraries into `tests/gen/game_soak`, substitutes a guarded terminal frame, builds via `lino_build.ps1`, and runs via `w7arun.ps1`. The 24-unit/96-byte telemetry contract checks exact frame count, changed `dzat`, progressed `pwr`, framebuffer coverage, clean process exit, and wall-time/FPS. A 5-frame smoke passed on 2026-08-08; multi-hour stability remains a later manual run.
3. **PLAYTEST.md checklist** - maintain the launch/target/fly/land/walk/name/save checklist. No interactive playtest is claimed as executed in this document.
4. **Polish backlog** - carry unresolved items below honestly.

## Open items from earlier waves (carry or close)

| # | Item | Wave 9 action |
|---|---|---|
| 1 | create_sky byte-exactness (7b sub-wave) | **CLOSED** - 16/16 sky suite PASS; canonical Python/C/Lino 27/27 cases, 408 records, exact anchors, and all declared mutants killed |
| 2 | Type-3 seed-flow/ground gap (7b) | Seed-flow theory RESOLVED: the captured 65,536-byte texture is exact for OCEAN/albedo 40/seed 0. The 39,710-byte `p_surfacemap` XFAIL remains, now bounded to `round_hill`/binary semantics and protected by a live sabotage check. |
| 3 | Wave 8 ip_reached follow-up | Algorithmically resolved: distinct `ap`/`ip` flags are implemented and graded. Live `game.txt` calls only the remote/Vimana MG loop, so the local approach is not integrated. |
| 4 | nsrun NSIN validation (OPENITEMS #4) | RESOLVED; validation fix is in place and geometry passes |
| 5 | pg_ref alfa!=0 (6a) | RESOLVED - the oracle was wrong, the port is correct |
| 6 | w5audit budget (4 voids) + fb_compare suite FAIL | Optional harness cleanup |
| 7 | Planetary geometry ungraded vs 1996 | Cannot close - no oracle; restate bound |
| 8 | genfp bare-fistp rule | Post-port; not Wave 9 |
| 9 | Doc typos (FLOATSITES label, GUIDE.BIN precondition) | **RESOLVED** -- FLOATSITES now names `SURFACE.BIN` for `NOCTIS-1.CPP:4179/4180`; recon README records that GUIDE.BIN must be absent for both the baseline and `w6c_redo.py` recapture/comparison |

Historical Wave-9 limit: `GMHALF=6` made that driver a 13x13 grid and its
texture was a procedural formula. The later iGUI game now uses generated
`p_background` textures for its two landable target bodies (type 8 and type 4)
and covers the source 64-tile circular visibility range with full-detail near
tiles plus grouped middle/far quads. The live landed path now also runs the
shared Felisian-crevasse/object-density pass and renders deterministic nearby
rocks plus the mirrored landing capsule, source proximity aperture, and its
three-range beacon. The capsule now follows the source gravity, bounce and
settling thresholds on descent, then seals and ascends back to the Stardrifter;
the bounded GUI probe covers that complete transition. Terrain generation and
the sky now share the target bodies' `149130`/`293154` seeds derived by the
source `(p_ray + p_orb_ray + p_orb_orient) * 4112` rule, rather than the old
surface-regression fixtures. Full-precision distant traversal, repeated rock clusters,
vegetation, animals, reflections, and ruins remain open. The bounded integrated soak is covered; multi-hour
stability remains open. `create_sky` is closed by the sky suite above. The
type-3 ground texture is exact while the measured heightmap XFAIL above remains
explicit.
