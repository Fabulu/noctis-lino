# FLOATSITES.md -- the quantisation registry

**Wave 3, Recon B. Read-only analysis of the Noctis IV+ R2.3 sources.
No implementation. This file is the durable deliverable; the previous
version of this registry existed only in an agent transcript and was lost.**

Subject: `C:\programmieren\noctis\niv-plus\source`, the three translation
units that are actually linked, plus the one header that is actually
included.

Analysis date: 2026-08-05. Every line number in this file was verified by
reading the file, not by memory.

---

## 0. Scope, method, and how to re-derive this

### 0.1 What is in the build -- verified, not assumed

`NOCTIS.MAK` links exactly three objects:

```
c0l.obj + noctis-0.obj + noctis-1.obj + noctis.obj
fp87.lib + mathl.lib + cl.lib
```

with `NOCTIS.CFG` = `-ml -3 -f287 -O -Oe -Ob -Z -k- -h -vi- ...`
(large model, 386 code, **hardware 287/387 -- not the emulator**, full
optimisation including `-Oe` global register allocation and `-Ob` dead-store
elimination, which is why intermediates stay on the x87 stack).

The include graph of those three units is:

| file | included by | in build? |
|---|---|---|
| `defs.h`, `noctis-d.h`, `noctis-0.h`, `noctis-2.h` | all three .CPP | **yes** |
| `TDPOLYGS.H` | `NOCTIS-0.CPP:720` | **yes** |
| `PITAGORA.H` | nothing | **no** |
| `FAST3D.H` | nothing | **no** |
| `TEXT3D.H` | nothing | **no** |
| `ASSEMBLY.H`, `GFX.H` | only the standalone tools | **no** |

### 0.2 The `_control87` decoy -- re-verified empirically

```
$ grep -n "fldcw|frndint|_control87|fstcw" TDPOLYGS.H NOCTIS-*.CPP NOCTIS.CPP PITAGORA.H
TDPOLYGS.H:139   _control87 (MCW_EM, MCW_EM);   // masks exceptions only
TDPOLYGS.H:1780  _control87 (MCW_EM, MCW_EM);   // masks exceptions only
PITAGORA.H:479   _control87 (MCW_EM, MCW_EM);
PITAGORA.H:480   _control87 (RC_CHOP, MCW_RC);  <-- NEVER EXECUTES
```

`PITAGORA.H` is in the source directory, is 78 KB, contains the only
`RC_CHOP` in the tree, and **is not included by anything in the build**.
The two `_control87` calls that do run touch `MCW_EM` only. **Rounding
control stays at 00 (nearest-even) for the whole program.** The 0x133F
control word read out of the shipped `NOCTIS.EXE` is therefore never
disturbed at run time.

Consequence, and it is the free win: every hand-written `fistp` rounds to
nearest-even. Only the compiler-generated C conversions chop, because
Borland's `__ftol` flips RC to 11 and back around each conversion.

Measured counts of hand-written FP→integer stores in the build:

```
fistp   36
fist     1     (TDPOLYGS.H:2632, inside the scanline loop of the 2-D clipper)
frndint  6     (NOCTIS-0.CPP:6361/6364/6367, NOCTIS.CPP:1602/1605/1608)
fild    26
```

**37 round-to-nearest FP→int stores, not 38.** `PORTPLAN.md` says 38; the
measured number is 37. The difference does not change the conclusion (lino's
`=,` under a round-to-nearest policy reproduces all of them for free) but the
figure in `PORTPLAN.md` should be corrected rather than propagated.

### 0.3 Reproduction

Scanners used are in the session scratchpad and are three short Python
files; they are trivially rebuildable from this description:

1. strip comments and string literals while preserving line numbers;
2. collect every identifier declared `float`/`double` and every identifier
   declared with an integer type; the intersection is the *ambiguous* set
   (58 names such as `x`, `y`, `d`, `k`, `r`, `cx`) which was reviewed by
   hand rather than trusted;
3. report (a) assignments whose LHS is integer-typed and whose RHS mentions
   a float-only name or a libm function; (b) calls to integer-parameter
   functions with float arguments; (c) `if`/`while`/`for`/`?:` lines
   mentioning a float-only name and a relational operator; (d) array
   subscripts and shift counts mentioning a float-only name.

Raw yields: **61** explicit integer-cast lines, **275** integer-assigned-
from-float lines, **80** float-argument-to-integer-parameter call sites,
**365** branch-selecting comparison lines, **10** float-derived array
subscripts, **34** shift lines touching a float name. Those are candidate
sets; everything below was then read in context and classified by hand.
The ambiguous-name set is why the raw numbers are larger than the
classified tables -- e.g. `(long)z` in `NOCTIS-1.CPP:1515` is an `int z`,
not the `float z` of another function, and is therefore *not* a float site.

### 0.4 Severity

| | meaning |
|---|---|
| **CRITICAL** | a wrong answer produces a *different universe*: a different seed, a different planet, a different scenario type, a star or a name that exists or does not. No tolerance exists. |
| **MAJOR** | a wrong answer changes visible geometry or content placement -- a tree in a different spot, a ring a layer thicker -- but the universe is the same one. |
| **COSMETIC** | a wrong answer moves a pixel. |

### 0.5 Conversion kinds

| tag | mechanism | rounding |
|---|---|---|
| `CAST-CHOP` | explicit C cast `(int)`/`(long)` | toward zero (`__ftol` flips RC to 11) |
| `ASSIGN-CHOP` | float expression assigned to an integer object | toward zero, then truncated to the object's width |
| `CALL-CHOP` | float expression passed to an integer parameter | toward zero, then **low 16 bits** for `int` params (Borland large model `int` = 16 bits) |
| `FISTP-NEAR` | hand-written x87 `fistp`/`fist` | nearest-even (RC stays 00) |
| `FRNDINT` | hand-written x87 `frndint` | nearest-even, result stays FP |
| `CMP` | float comparison selecting a branch or loop bound | -- |
| `INDEX` / `SHIFT` | float value reaching an array subscript or a shift count | via one of the above |

`ASSIGN-CHOP` to an `int` object and `CALL-CHOP` to an `int` parameter are
the same machine sequence: `__ftol` produces a 32-bit result and the low 16
bits are taken. **Wraparound is defined behaviour here and must be
reproduced** -- §4.2 shows it is a normal path, not a corner case.

---

## 1. The seeds -- every site where a float becomes an integer seed

This is the section that decides whether the port generates the same
universe. Ordered by blast radius.

### 1.1 `nearstar_identity` -- the root of everything

```
NOCTIS-0.CPP:4078   nearstar_identity = nearstar_x/100000*nearstar_y/100000*nearstar_z/100000;
NOCTIS-0.CPP:3970   srand (ap_target_x/100000*ap_target_y/100000*ap_target_z/100000);
NOCTIS.CPP:1244     ap_target_id = ap_target_x / 100000 * ap_target_y / 100000 * ap_target_z / 100000;
```

C associativity makes this **`((((x/1e5) * y) / 1e5) * z) / 1e5`** -- five
operations, not "three divides then two multiplies". Under `-f287 -O` the
whole chain lives on the x87 stack at 64-bit mantissa and is rounded to 53
bits exactly once, at the store into the `double`.

**Inputs are exact integers.** Traced to origin: `ap_target_x` is only ever
assigned from `targets_table_px[]` (`NOCTIS.CPP:4326`), which is
`laststar_x` (`NOCTIS-0.CPP:5771`), which `isthere` produces with
`fild dword ptr laststar_x` / `fst laststar_x` -- an int32 sector coordinate
materialised as a double; or from `atol(manual_x_string)`
(`NOCTIS.CPP:4434`); or read from `Current.BIN` as 8 raw bytes. There is no
path by which a star coordinate is a non-integer.

So `nearstar_identity` is a **pure function of three int32 values** through
five correctly-rounded extended-precision operations. That is a very
tractable target -- no accumulated state, no history.

| consumer | site | kind | severity |
|---|---|---|---|
| `search_id_code (nearstar_identity + n, 'P')` -- does this planet have a name? | `NOCTIS-0.CPP:4367` | CMP (window) | **CRITICAL** |
| `current_planet_id = nearstar_identity + ip_targetted + 1` | `NOCTIS.CPP:1263`, `1808` | -- | **CRITICAL** |
| `srand (nearstar_identity)` | `NOCTIS.CPP:3104`, `3395` | CALL-CHOP → int16 | **CRITICAL** |
| `fast_srand (nearstar_identity)` | `NOCTIS.CPP:3672`, `3726` | CALL-CHOP → long | MAJOR |
| `unsigned seed = nearstar_identity * 12345` (`load_starface`) | `NOCTIS-0.CPP:6048` | ASSIGN-CHOP → uint16 | MAJOR |
| `(long)(nearstar_identity * 1E6) == -37828` -- **is this star Balastrackonastreya?** | `NOCTIS-1.CPP:2644` | CAST-CHOP + CMP | **CRITICAL** |
| `(long)(nearstar_identity * 1E5) == 1599551984L` -- **is this Fenia?** | `NOCTIS-1.CPP:2667` | CAST-CHOP + CMP | **CRITICAL** |
| `(long)(nearstar_identity * 1E8) == -11543634L` -- **is this Ylastravenia?** | `NOCTIS-1.CPP:2683` | CAST-CHOP + CMP | **CRITICAL** |
| `ap_target_id == nearstar_identity` | `NOCTIS.CPP:2842` | CMP (exact equality of two doubles) | MAJOR |

The three `1E6`/`1E5`/`1E8` equalities are the author's hand-placed story
worlds -- Felysia, Peach, Pleasance, Wetwick, Suricrasia and the Suricrasian
Cube. **One ULP in the identity and the ruins do not exist.** They are also
the sharpest available test: three known-answer equalities on three known
stars.

### 1.2 `isthere` -- the sensor window, and it uses a *different formula*

```
NOCTIS-0.CPP:5636-5722   char isthere (double star_id)
```

The body is hand-written x87:

```
fild dword ptr laststar_x ; fst laststar_x ; fmul idscale
fild dword ptr laststar_y ; fst laststar_y ; fmul idscale
fild dword ptr laststar_z ; fst laststar_z ; fmul idscale
fmulp                      ; ST = (y*ids)*(z*ids)
fmulp                      ; ST = (x*ids)*((y*ids)*(z*ids))
fst laststar_id
fcomp sidlow  / fstsw / sahf / jb ...
fld laststar_id / fcomp sidhigh / ...
```

with `idscale = 0.00001` (`NOCTIS-0.CPP:4000`) and
`sidlow = star_id - idscale`, `sidhigh = star_id + idscale`
(`:5643-5644`).

Two things matter and both are easy to get wrong:

1. **It multiplies by `0.00001`; `nearstar_identity` divides by `100000`.**
   `100000` is exactly representable, `0.00001` is not. The association is
   also different -- `(x·s)·((y·s)·(z·s))` versus `((((x/1e5)·y)/1e5)·z)/1e5`.
   The two formulas are *not* the same function.
2. **The comparison reads ST(0), not the stored double.** `fst laststar_id`
   rounds to 53 bits for the memory copy, but `fcomp sidlow` compares the
   still-80-bit register. The window test is an extended-precision test.

Measured consequence (IEEE-double model, this machine):

```
|coord|   identity     ULP(id)      window(1e-5) in ULPs
1e5       1            2.22e-16     4.5e+10
1e7       1e6          1.16e-10     8.6e+04
1e8       1e9          1.19e-07     83.9
3.6e8     4.67e10      7.63e-06     1.31      <-- window == 1 ULP here
1e9       1e12         1.22e-04     0.082
2e9       8e12         9.77e-04     0.010
```

Beyond roughly **3.6e8 units per axis the ±1e-5 window is narrower than one
ULP**, so the test degenerates into strict equality. And because the two
formulas differ by about 1 ULP:

```
fraction of stars whose stored id cannot be re-found by isthere
  R=1e6 .. 1e8 : 0.00 %
  R=1e9        : 0.26 %
  R=2e9        : 26.41 %      (20 000 random sector coords per row)
```

**A quarter of named stars near the galactic rim are unreachable by the
sensor sweep in the original.** That is vanilla behaviour, not a bug to fix.
A port that "cleans up" the two formulas into one will make those stars
reappear and will not match the game.

| site | kind | severity |
|---|---|---|
| `NOCTIS-0.CPP:5649-5651` `sect_x/y/z = (dzat_x - visible_sectors*50000)/100000` → `long` | ASSIGN-CHOP (toward zero, **not** floor -- asymmetric across 0) | **CRITICAL** |
| `NOCTIS-0.CPP:5703-5716` the `fcomp sidlow` / `fcomp sidhigh` pair | CMP at 80 bits | **CRITICAL** |
| `NOCTIS-0.CPP:4022` `buffer_double[index] > id_low && < id_high` in `search_id_code` | CMP (doubles read from `STARMAP.BIN`) | **CRITICAL** |

`search_id_code`'s window is the *C-level* twin of the same test, comparing
against 53-bit doubles loaded from the file, so its two operands are both
plain doubles -- but `id_low`/`id_high` are formed by `id_code ∓ idscale`
in x87 and the compare is against an 80-bit register there too.

### 1.3 `seedval` -- the planet-surface seed

```
NOCTIS-0.CPP:4766   void surface (int logical_id, int type, double seedval, unsigned char colorbase)
NOCTIS-0.CPP:4784       fast_srand (seedval + 4112);
NOCTIS-0.CPP:4811       fast_srand (seedval * 10);
```

Four call sites, all in `planets()`:

```
NOCTIS-0.CPP:5380  moon, type!=0 : 1000000 * nearstar_ray * nearstar_p_type[n] * nearstar_p_orb_orient[n]
NOCTIS-0.CPP:5388  moon, type==0 : 2000000 * n * nearstar_ray * nearstar_p_orb_orient[n]
NOCTIS-0.CPP:5397  planet,type!=0: 1000000 * nearstar_p_type[n] * nearstar_p_orb_seed[n]
                                  * nearstar_p_orb_tilt[n] * nearstar_p_orb_ecc[n]
                                  * nearstar_p_orb_orient[n]
NOCTIS-0.CPP:5407  planet,type==0: 2000000 * n * nearstar_p_orb_seed[n]
                                  * nearstar_p_orb_tilt[n] * nearstar_p_orb_ecc[n]
                                  * nearstar_p_orb_orient[n]
```

Five and six-factor products, evaluated left to right on the x87 stack,
passed as a `double`, then chopped twice -- once for `seedval + 4112` and
once for `seedval * 10`. `fast_srand` takes a `long`, so this is a 32-bit
chop, not 16.

**Severity: CRITICAL.** The whole surface bitmap, the rotation period, the
terminator, and (through `nearstar_p_rotation`) the night zone come from
these two seeds.

`fast_srand` then does `or word ptr seed, 3` -- it forces the low two bits.
That absorbs a ±1 error in the seed *only when the error does not cross a
multiple of 4*. It is a partial, unreliable cushion; do not rely on it.

### 1.4 `global_surface_seed` -- the terrain seed

```
NOCTIS-1.CPP:3671   global_surface_seed = (nearstar_p_ray[ip_targetted]
                                         + nearstar_p_orb_ray[ip_targetted]
                                         + nearstar_p_orb_orient[ip_targetted]) * 4112;
NOCTIS-1.CPP:3676   srand (global_surface_seed + landing_pt_lon);
NOCTIS-1.CPP:3677   if (latitude > 25 + (global_surface_seed % 15) + random(5))
NOCTIS-1.CPP:3678       global_surface_seed++;
```

Two adds and a multiply on the x87 stack, then `ASSIGN-CHOP` into a `long`.
Consumed by `fast_srand`/`srand` at `NOCTIS-1.CPP:1974`, `1975`, `2795`,
`2796`, `3171`, `3172`, `3248`, and `1131`
(`fast_srand (h1 + global_surface_seed)` in the ground renderer).

**Severity: CRITICAL.** This is the seed for `build_surface` -- the entire
200×200 heightmap, the object chart, the trees, the ruins.

Note the conditional `++` at `:3678`: the latitude test is *exact* (see
§4.1), so the increment is not itself a float hazard; the hazard is entirely
in the truncation at `:3671`.

### 1.5 The other seed sites

| site | expression | decides | kind | severity |
|---|---|---|---|---|
| `NOCTIS-0.CPP:4051` | `srand ((long)star_x%10000*(long)star_y%10000*(long)star_z%10000)` in `starnop` | estimated planet count shown in the datasheet | CAST-CHOP ×3 then integer | **CRITICAL** (see §3.1 -- fully reducible) |
| `NOCTIS-0.CPP:4080` | same expression in `prepare_nearstar` | **the entire planetary system** | CAST-CHOP ×3 | **CRITICAL** |
| `NOCTIS-0.CPP:5478` | `fast_srand (nearstar_p_orb_seed[n] * nearstar_p_orb_ecc[n] * 12345)` | sky colour filters at the landing site | CALL-CHOP → long | MAJOR |
| `NOCTIS-0.CPP:5209` | `fast_srand (10000 * ringray + planet_id)` | ring particle layout | CALL-CHOP → long | MAJOR |
| `NOCTIS-1.CPP:138` | `fast_srand (((long)x>>14) + ((long)y>>14) + ((long)z>>14))` in `greenmush`, `x/y/z` are `float` | where vegetation clumps sit | CAST-CHOP ×3 + SHIFT | MAJOR |
| `NOCTIS-1.CPP:4078` | `fast_srand (((long)(pos_x)>>10) + ((long)(pos_z)>>10))` | ground detail at the walker's position | CAST-CHOP + SHIFT | MAJOR |
| `NOCTIS-1.CPP:4082` | `fast_srand (pos_x+pos_z+clock()*3)` | -- | CALL-CHOP | COSMETIC (clock-driven) |
| `NOCTIS.CPP:2999` | `fast_srand ((long)ap_target_x%32000)` | substellar mass jitter in the datasheet | CAST-CHOP | COSMETIC (display only -- **but it perturbs the shared `flat_rnd_seed`**, see §5.4) |
| `NOCTIS.CPP:2543` / `2555` | `fast_srand (nearstar_z)` / `fast_srand (ir + nearstar_x)` | star-surface flicker | CALL-CHOP | COSMETIC |
| `NOCTIS-0.CPP:1075` | `fast_srand (long seed)` itself: `or word ptr seed, 3` | -- | -- | forces low 2 bits; not a rounding cushion |
| `NOCTIS.CPP:658`, `2046`, `2358`, `3093`, `3137`, `3470`, `3575`; `NOCTIS-1.CPP:3224`, `3225`, `3758` | `srand/fast_srand (secs …)` | animations | CALL-CHOP | COSMETIC (wall-clock driven) |
| `NOCTIS-1.CPP:2051`, `2641` | `fast_srand (landing_pt_lat * landing_pt_lon)` | landing-site environment | pure integer | -- (no float) |

---

## 2. Float → integer conversions, complete by kind

### 2.1 Explicit casts of a float expression

Excluding the 61-line raw grep's false positives (`(long)(p_surfacemap[…])`,
`(long)z`/`(long)fz` where the variable is an `int`, `(int)missingdigits`,
`(unsigned char)b`, `farmalloc((long)TEXTURE_YSIZE …)`), the genuine
float→integer casts are:

| site | expression | decides | severity |
|---|---|---|---|
| `NOCTIS-0.CPP:3366`, `3598` | `pixptr = riga[(int)yy] + (int)xx` | pixel address in the lens-flare blitter | COSMETIC |
| `NOCTIS-0.CPP:3807` | `vptr = 320*(int)pyy + pxx` | pixel address in `far_pixel_at` | COSMETIC |
| `NOCTIS-0.CPP:3934` | `secs = secs*365 + (long)(secs/4)` | leap-day count in the epoch clock | MAJOR (wrong date → wrong `secs` → wrong orbital phase everywhere) |
| `NOCTIS-0.CPP:4051`, `4080` | `(long)star_x`, `(long)nearstar_x`, … | §1.5 | **CRITICAL** |
| `NOCTIS-0.CPP:4890`, `4933`, `4982`, `5023` | `cx = ((long)(k*secs) / (ranged_fast_random(N)+M)) % 360` | cloud-band rotation phase | COSMETIC |
| `NOCTIS-0.CPP:6228`, `6230` | `(((long)(pos_x)) >> 14) - 100` | the ground-position readout in the HUD | COSMETIC |
| `NOCTIS-0.CPP:6445` | `if (iqsecs < (long)secs)` | one-second tick edge | COSMETIC |
| `NOCTIS-1.CPP:1088` | `long depth = (long)(hpdep) >> 14` | ground-quad LOD selection | MAJOR |
| `NOCTIS-1.CPP:1263` | `cl = 1536 - ((long)(hpdep) >> 5)` | ground shading band | COSMETIC |
| `NOCTIS-1.CPP:2644`, `2667`, `2683` | `(long)(nearstar_identity * 1E{6,5,8})` | **which story world this is** | **CRITICAL** |
| `NOCTIS-1.CPP:3939` | `ptr = ((int)(5*beta)%5) - 320*((int)(4*(alfa+180))%4) - 4` | sub-pixel background offset | COSMETIC |
| `NOCTIS-1.CPP:3940` | `ptr -= (int)(beta / 72) * 320` | background row | COSMETIC |
| `NOCTIS-1.CPP:3942` | `background (360*(int)(alfa+51)-(int)(beta)%360, …)` | background scroll origin | COSMETIC |
| `NOCTIS-1.CPP:4063`, `4064`, `4311`, `4312` | `ipfx = ((long)(cam_x)) >> 14` | which surface quadrant the camera is in | MAJOR |
| `NOCTIS-1.CPP:4078` | `((long)(pos_x)>>10) + ((long)(pos_z)>>10)` | §1.5 | MAJOR |
| `NOCTIS-1.CPP:4176`, `4177` | `pos_x = ((((long)pos_x) >> 14) << 14) + 8192` | **snaps the walker to a quadrant centre** | MAJOR |
| `NOCTIS-1.CPP:4179`, `4180` | `atl_x = ((long)pos_x) >> 14` | the saved atlas coordinate (`SURFACE.BIN`) | MAJOR |
| `NOCTIS.CPP:265` | `_SI = 320*(int)ry + rx` | pixel address | COSMETIC |
| `NOCTIS.CPP:1616`, `1618` | `(int)(sin(deg*navigation_beta)*+100)` | heading readout | COSMETIC |
| `NOCTIS.CPP:2999` | `(long)ap_target_x%32000` | §1.5 | COSMETIC |
| `NOCTIS.CPP:3069` | `p4 = (long)(tmp_float) % 1000` | revolution-period readout | COSMETIC |
| `NOCTIS.CPP:3802` | `if ((long)secs%300 == 0)` | 5-minute autosave edge | MAJOR (a missed edge loses the save) |

### 2.2 Implicit narrowing at a call boundary

Wave 2 settled the semantics: `unknown1.verdict = NARROWED_AT_CALL_BOUNDARY`
-- the `double` is chopped by `__ftol` and truncated to `int16` before the
callee sees it, uniformly, because `rand` has exactly one caller and
`random()` was therefore compiled as a real function rather than expanded
per site.

**The generation sites -- these are the ones that build planets:**

| site | expression | int16 overflow? | severity |
|---|---|---|---|
| `NOCTIS-0.CPP:4089` | `random (300 * nearstar_ray)` | no (max 10 500) | **CRITICAL** |
| `NOCTIS-0.CPP:4090`, `4091` | `zrandom (10*nearstar_p_orb_seed[n])` | **YES -- see §4.2** | **CRITICAL** |
| `NOCTIS-0.CPP:4092` | `random (nearstar_p_orb_seed[n] + 10*fabs(nearstar_p_orb_tilt[n]))` | no (max ≈ 21 800) | **CRITICAL** |
| `NOCTIS-0.CPP:4093` | `random (nearstar_p_orb_seed[n])` | no | **CRITICAL** |
| `NOCTIS-0.CPP:4094` | `zrandom (nearstar_p_ray[n])` | no (ray < 1) | **CRITICAL** |
| `NOCTIS-0.CPP:4195` | `zrandom (300 * nearstar_p_ray[n])` | no | **CRITICAL** |
| `NOCTIS-0.CPP:4196`, `4197` | `zrandom (10*nearstar_p_orb_seed[q])` (moons) | possible | **CRITICAL** |
| `NOCTIS-0.CPP:4198` | `random (nearstar_p_orb_seed[q] + 10*fabs(nearstar_p_orb_tilt[q]))` | possible | **CRITICAL** |
| `NOCTIS-0.CPP:4199` | `random (nearstar_p_orb_seed[n])` -- note `[n]`, the **planet's** seed inside the moon loop | after the `*= 10` at `:4106`, possible | **CRITICAL** |
| `NOCTIS-1.CPP:4464` | `random (150 / rainy)` | no; but see §5.3 | MAJOR |

`zrandom` itself (`NOCTIS-0.CPP:3987`) is
`float zrandom (int range) { return (random(range) - random(range)); }` --
`int` parameter, so everything *inside* is integer. Wave 2 settled the
order: `unknown2.verdict = LEFT_TO_RIGHT`, first draw minus second, fixed in
its single compiled body.

**Non-generation call-boundary narrowings** (float argument to a
`double`/`float` parameter is not a narrowing and is excluded; these are the
ones that lose bits): `globe`/`glowinglobe`'s `float mag_factor` receiving a
`double` (`NOCTIS-0.CPP:3043`, `3173`), `ring`'s `double ox,oy,oz` receiving
`plx/ply/plz` (fine -- same width), `surface`'s `double seedval` receiving
the products (fine -- same width). The one that *does* narrow is
`mag_factor`: `nearstar_p_ray[n]` is a `double` and `mag_factor` is a
`float`, so every globe draw quantises the apparent radius to 24 bits
(`NOCTIS-0.CPP:5564`, `5592`, `5599`). COSMETIC, but it is a deliberate
narrowing and must be preserved.

### 2.3 Assignment of a float expression to an integer object

Only the ones that decide something are listed; the full raw set is 275
lines, most of them float-to-float in the ambiguous-name space.

| site | expression | decides | severity |
|---|---|---|---|
| `NOCTIS-0.CPP:2804` | `rarity_factor = distance_from_home * 0.25e-8` then `rarity_factor = 1 << rarity_factor` | **which stars exist at all** | **CRITICAL** -- §3.4 |
| `NOCTIS-0.CPP:2808-2810` | `sect_x = (dzat_x - visible_sectors*50000) / 100000` (in `stars()`) | the sector scan window | **CRITICAL** |
| `NOCTIS-0.CPP:5649-5651` | the same three lines in `isthere` | ditto | **CRITICAL** |
| `NOCTIS-1.CPP:3636` | `cpos = 555 * nearstar_p_orb_orient[ip_targetted]` → `long`; `sctype = (cpos % 4) + 1` | **desert / ocean / icy / plain** -- the felisian scenario | **CRITICAL** -- §3.2 |
| `NOCTIS-1.CPP:3671` | `global_surface_seed = (…) * 4112` | §1.4 | **CRITICAL** |
| `NOCTIS-0.CPP:4795` | `nearstar_p_rotation[l] = secs / nearstar_p_rtperiod[l]` → **`int` (16-bit)** then `%= 360` | planet rotation phase → terminator → night zone → `albedo` → `sctype` | **CRITICAL** (and it wraps: `secs` is ~6e11, so the quotient routinely exceeds int16 -- the wrap is the behaviour) |
| `NOCTIS-0.CPP:3962` | `epoc = 6011 + secs / 1e9` → `int` | the epoch number in the HUD and the console | MAJOR |
| `NOCTIS-0.CPP:5340` | `ringlayers = 0.05 * (d3 / nearstar_p_ray[n])` → `int` | ring layer count | MAJOR |
| `NOCTIS-0.CPP:5368` | `plwp = 359 - planet_viewpoint (dzat_x, dzat_z)` | ring / terminator orientation | MAJOR -- §3.3 |
| `NOCTIS-0.CPP:4801` | `plwp = 89 - cplx_planet_viewpoint (logical_id)` → `nearstar_p_term_start/end` | **the day/night terminator, hence `nightzone`, hence `albedo`, hence `sctype`** | **CRITICAL** |
| `NOCTIS-1.CPP:3546` | `plwp = 89 - planet_viewpoint (secondary_nearstar_x, secondary_nearstar_z)` | secondary-sun terminator | MAJOR |
| `NOCTIS-1.CPP:3692`, `3694` | `s_background[vptr] = crcy` / `crcy / 2` where `crcy` is `float` | sky gradient bytes | COSMETIC |
| `NOCTIS-1.CPP:1515-1524` | `y += p_surfacemap[…]` (float) … `p_surfacemap[…] = y` | **terrain height bytes** -- `mountain()` | MAJOR |
| `NOCTIS-1.CPP:1568-1583` | same pattern in the ridge/valley generator, with `pow(y, h_raiser)` | terrain height bytes | MAJOR |
| `NOCTIS-1.CPP:796`, `797`, `3240`, `3241` | `sqc_x = ani_x[n] / 16384` → `int` | which surface square an animal is in | MAJOR |
| `NOCTIS-1.CPP:1658`, `1659` | `shift_x = cos(ang)*shift_d + x` → `int` | crater rim pixel walk | COSMETIC |
| `NOCTIS-1.CPP:1930`, `1931` | `ai = sqrt(ai)` → `int`; `peak = 3*hr*cos(M_PI_2*(double)ai/(double)ra)` → `int` | crater profile | COSMETIC |
| `NOCTIS-1.CPP:4084`, `4093` | `flicks = fabs(wp*50) + 100` → `int` | lightning flicker count | COSMETIC |
| `NOCTIS-1.CPP:4489` | `waveratio = 10 - fabs(step)/5` → `int` | wake wave spacing | COSMETIC |
| `NOCTIS.CPP:2081` | `pwr = dpwr` (`double` → `int`) | **ship power**, threshold-tested in ~12 places against the +15000 bias | MAJOR |
| `NOCTIS.CPP:2601` | `ir = ((1600*nearstar_ray) - l_dsd) / (100*nearstar_ray)` → `int` | star-glow intensity index | COSMETIC |
| `NOCTIS.CPP:2657`, `2672`, `2721` | `s_control = (cam_y+25)/50 + 3`, `s_command = …`, `active_screen = (pos_z + 104*15)/(-54*15)` | **which cockpit control the cursor is on / which screen is active** | MAJOR (a wrong answer presses the wrong button) |
| `NOCTIS.CPP:2798` | `entity = dxx` | vimana drive step size | MAJOR |
| `NOCTIS.CPP:3066-3068` | `p1 = tmp_float*1e-9`, … | period readout | COSMETIC |
| `NOCTIS.CPP:3108`, `3112`, `3398`, `3402` | `ir -= 125 / dsd` | glow intensity | COSMETIC |
| `NOCTIS.CPP:3261`, `3357` | `pwr -= l_dsd * 1E-5` | fuel burn per tick | MAJOR (accumulates) |
| `NOCTIS.CPP:3496-3516` | `ir3 = ilight + 30 - clock()%30 + l_dsd` etc. | palette entries | COSMETIC |
| `NOCTIS.CPP:1594`, `1596`, `1598`; `NOCTIS-0.CPP:6216-6220` | `lsecs = secs; lsecs %= …` | triad clock readout | COSMETIC |
| `NOCTIS-0.CPP:1167`, `1176`, `1185` | `palette_buffer[…] = start_r` (float → uchar) | palette fade | COSMETIC |
| `NOCTIS-0.CPP:6235` | `cpos = ccom / 9; crem = ccom * 0.44444` | compass glyph selection | COSMETIC |

### 2.4 The 37 hand-written `fistp`/`fist` sites -- round-to-nearest

All are in the renderer. All get lino's `=,` semantics for free under a
round-to-nearest policy. Listed here so the registry is complete, not
because any of them is dangerous.

| file:lines | function | what it produces |
|---|---|---|
| `TDPOLYGS.H:721`, `731` | `poly3d` perspective projector (clipped path) | screen x/y and the running bbox |
| `TDPOLYGS.H:1353`, `1357`, `1379`, `1383`, `1418`, `1422`, `1428`, `1430` | `poly3d` 2-D clipper vertex insertion | clipped vertex screen coords |
| `TDPOLYGS.H:2456`, `2459` | `polymap` projector | screen x/y |
| `TDPOLYGS.H:2605`, `2632` | scanline edge walk (`fist bndx` inside the loop) | left/right span limits |
| `TDPOLYGS.H:2737`, `2738`, `2799`, `2800`, `2935`, `2936` | affine/perspective texture mapper | `u`, `v` texel coordinates |
| `TDPOLYGS.H:3194`, `3197` | `getcoords` | `_x_`, `_y_`, then a bounds test that decides **whether a surface object is drawn at all** -- MAJOR, not cosmetic |
| `NOCTIS-0.CPP:1892`, `1894`, `1899`, `1901`, `2060`, `2062` | `stick3d` endpoints | line endpoints |
| `NOCTIS-0.CPP:2892`, `2907`, `2929`, `2953` | `stars()` star projection | star pixel position (**decides whether a star is on screen**) |
| `NOCTIS-0.CPP:3107`, `3122`, `3241`, `3257` | `globe` / `glowinglobe` | globe sample coordinates |
| `NOCTIS-0.CPP:4581` | `spot` | surface feature centre |

Plus six `frndint` (`NOCTIS-0.CPP:6361/6364/6367`, `NOCTIS.CPP:1602/1605/1608`)
rounding `dzat_x/y/z` into `parsis_x/y/z` for the coordinate readout and for
the console's "set target to parsis" round trip.

---

## 3. Integer reduction -- which CRITICAL sites need no real arithmetic

This is the analysis the wave was asked for. Result: **more reduces than
expected, and the residue is small and well-shaped.**

### 3.1 Fully reducible to exact integer arithmetic

**(a) `srand ((long)x%10000*(long)y%10000*(long)z%10000)`** --
`NOCTIS-0.CPP:4051`, `4080`.
The inputs are exact integers (§1.1). `(long)` of an exact integer is exact.
Everything after is `long`. **No floating point is required at all.**

Two traps, both easy to get wrong and both fatal:
* C precedence makes this
  `((((((long)x % 10000) * (long)y) % 10000) * (long)z) % 10000)` --
  *not* the product of three residues.
* The multiplies are 32-bit `long` and wrap. `(long)y` can be ±2e9, so
  `residue * y` overflows routinely; the wrap is the behaviour.
* `srand` takes `unsigned` = 16 bits, so only the low half survives.

**(b) `nearstar_p_orb_orient[n] = deg * random(360)`** -- `NOCTIS-0.CPP:4088`,
`:4194`. `deg` is the compile-time constant `M_PI/180`. The argument to
`random` is `360`, an `int`. Therefore **`orb_orient` is always one of
exactly 360 known double values.** It is a 360-entry constant table, not a
computation. Every downstream use of `orb_orient` alone can be tabulated.

**(c) `cpos = 555 * orb_orient; sctype = (cpos % 4) + 1`** --
`NOCTIS-1.CPP:3636-3637`, the felisian scenario selector.
Combining (b): `cpos` takes 360 possible values, verified by direct
computation:

```
k :   0   1   2   3   4   5   6   7   8   9  10  11 …
cpos: 0   9  19  29  38  48  58  67  77  87  96 106 …
sctype 1  2   4   2   3   1   3   4   2   4   1   3 …
```

all four `sctype` values occur. **This CRITICAL site reduces to a 360-entry
`char` lookup table with zero floating point.** (The `k=0` entry sits exactly
on a boundary -- `v = 0.0`, `cpos = 0` -- but that is exact in every
arithmetic, not a hazard.)

**(d) `latitude`** -- `NOCTIS-1.CPP:3474`:
`latitude = (float)(abs(landing_pt_lat - 60)) * 1.5`.
`landing_pt_lat` ∈ [1,119], so `latitude` ∈ {0, 1.5, 3.0, …, 90.0} -- 61
values, all exactly representable in binary (verified). Every comparison
against it (`> 75`, `> 60`, `> 45`, `> 25 + (seed%15) + random(5)` at
`NOCTIS-1.CPP:1988`, `2004`, `3645`, `3646`, `3677`) is therefore **exact in
any arithmetic**. Reduce by carrying `3*abs(lat-60)` as an integer and
doubling the thresholds. **No float needed anywhere in the latitude path.**

**(e) `albedo`** -- `NOCTIS-0.CPP:5498-5512`. Byte reads, shifts, and an
integer subtract. `int` throughout. The `if (albedo < 25) sctype = OCEAN`
test at `NOCTIS-1.CPP:3641` is pure integer. **No float.**

**(f) `fast_srand (landing_pt_lat * landing_pt_lon)`** -- `NOCTIS-1.CPP:2051`,
`2641`, and `srand (landing_pt_lon * landing_pt_lat)` at `NOCTIS-1.CPP:3634`. Both `int`.
**No float.**

**(g) `zrandom`'s interior** -- `NOCTIS-0.CPP:3987`. `int` parameter, and
Borland's `random(num)` with an integer `num` is
`(int)(((long)rand()*(num))/(RAND_MAX+1))` -- all integer. Confirmed by Wave 2.
Only the *argument expression* at each call site is float.

**(h) `rainy = (float)atmosphere[ptr>>1] * 0.25`** -- `NOCTIS-0.CPP:5513`.
`0.25` is a power of two and the operand is a byte, so this is exact:
`rainy ∈ {0, 0.25, …, 63.75}`, clamped to 5. Carry it as an integer count of
quarters. The subsequent `rainy /= random(4)+1` and `/= random(3)+2` are
*not* exact (÷3 is not) -- see §3.5.

### 3.2 Reducible to a small enumerable table (one correctly-rounded op each)

These are not integer, but they are not chains either: each is one or two
correctly-rounded operations applied to an exact integer, so the whole
codomain can be precomputed and stored, or evaluated with a two-op
soft-float and no accumulated state.

| value | expression | domain size |
|---|---|---|
| `ap_target_ray` (`NOCTIS-0.CPP:3973`) | `(float)((double)(class_ray[c] + random(rayvar[c])) * 0.001)` -- the sum of two `int`s is exact, one double multiply, one round to `float` | ≤ 35 001 distinct values; verified all 35 001 are distinct floats |
| `nearstar_p_orb_ecc[n]` (`:4092`) | `1 - (double)random(…) / 2000` | ≤ 32 768 |
| `nearstar_p_ray[n]` first pass (`:4093`) | `(double)random(…) * 0.001 + 0.01` | ≤ 32 768 |
| `nearstar_p_tilt[n]` (`:4090`) | `zrandom(…) / 500` -- `zrandom` returns an exact integer as `float` | ≤ 65 535 (double-rounding 64→53 must be reproduced) |
| `nearstar_p_orb_tilt[n]` (`:4091`) | `zrandom(…) / 5000` | ≤ 65 535 |
| `flandom()` (`:1110`) | `(float)random(32767) * 0.000030518` | ≤ 32 768 |
| `fast_flandom()` (`:1112`) | `(float)fast_random(32767) * 0.000030518` | ≤ 32 768 |
| `cos(deg*a)`, `sin(deg*a)` in `planet_viewpoint` (`:1504-1505`) | argument is `deg * (double)a`, `a` ∈ [0,359] | **360 entries** -- the transcendental only ever sees 360 arguments |
| `cos(beta)`, `sin(beta)` in `planet_xyz` (`:1451-1452`) where `beta = nearstar_p_orb_orient[n]` | same 360 arguments as above | **360 entries** |

The last two are the most valuable: they remove Borland's `sin`/`cos`
implementation from the critical path entirely. A port needs 360 correctly-
rounded sine and cosine values, obtainable once and checked, instead of a
bit-compatible transcendental library.

### 3.3 Reducible to *one* correctly-rounded operation plus exact integer work

| site | reduction |
|---|---|
| `sect_x/y/z = (dzat_x - k) / 100000` → `long` (`NOCTIS-0.CPP:2808-2810`, `5649-5651`) | one double subtract, one double divide, then an exact chop-toward-zero. No chain. |
| `nearstar_p_rotation[l] = secs / rtperiod[l]` (`:4795`) | one double divide of a double by an `int`, then chop to int32 and take the low 16 bits, then `%= 360`. |
| `epoc = 6011 + secs / 1e9` (`:3962`) | one divide, one add, one chop. |
| `global_surface_seed = (a+b+c) * 4112` (`NOCTIS-1.CPP:3671`) | two adds and a multiply -- but on values that are themselves chain outputs (§3.4). |
| `(long)(nearstar_identity * 1E{6,5,8})` (`NOCTIS-1.CPP:2644`, `2667`, `2683`) | one multiply and a chop -- but on `nearstar_identity` (§3.4). |

### 3.4 Genuinely needs real-number arithmetic at extended precision

Nothing below reduces. These are the sites where an 80-bit engine (or a
soft-float that reproduces 64-bit-mantissa intermediates) is mandatory.

1. **`nearstar_identity` / `ap_target_id`** -- five chained ops on three
   exact int32 inputs, rounded once at the store (§1.1). The killer oracle
   (`STARMAP.BIN`, 4194/4194) tests exactly this.
2. **`isthere`'s identity and its two window compares** -- different formula,
   different association, compare against a still-80-bit register (§1.2).
3. **`search_id_code`'s window compare** -- `id_code ∓ idscale` and two
   compares (`NOCTIS-0.CPP:4011-4012`, `4022-4023`).
4. **`rarity_factor`** -- `sqrt(x²+z²) + 30·|y|`, then `× 0.25e-8`, then chop,
   then `1 <<` (`NOCTIS-0.CPP:2802-2806`). A `sqrt`; not reducible. The
   boundary lands at `distance_from_home = 4e9·k`, so the chance of sitting
   on it is tiny -- but the shift decides *which stars exist*, so it is
   CRITICAL by consequence even though its failure probability is low.
5. **`nearstar_p_orb_seed[n]`** -- `NOCTIS-0.CPP:4089`:
   `3 * (n*n+1) * nearstar_ray + (float) random (300 * nearstar_ray) / 100`.
   `nearstar_ray` is a `float` and the `(float)` cast is a **deliberate
   mid-expression narrowing**. Under `-f287 -O` Borland will keep the sum on
   the stack, so where exactly the narrowing lands is a spill-schedule
   question, not a source question. **This is the single most schedule-
   sensitive line in the generation path** and it is upstream of everything
   else about the planet. It needs the Wave 2 transcription, not a guess.
6. **`key_radius` accumulation and `nearstar_p_orb_ray[n]`** --
   `NOCTIS-0.CPP:4301-4341`. A running sum in `double` over up to 20 planets,
   with `0.22` / `0.12` / `0.025` branch weights. Genuinely stateful; each
   planet's orbit depends on every inner planet's. Feeds `global_surface_seed`.
7. **`seedval` products** -- five and six factors (§1.3).
8. **`s_m` and `planet_xyz`** -- `qt_M_PI * ray³ * 0.01e-7`, then
   `sqrt(s_m/ors)`, then `sin`/`cos` of `orb_tilt*deg` (**not** tabulatable --
   `orb_tilt` is a real). Feeds `plx/ply/plz`, hence `planet_viewpoint`,
   hence the terminator.
9. **`planet_viewpoint`'s 360-way argmin** -- `NOCTIS-0.CPP:1503-1511`. The
   trig reduces (§3.2) but the comparison `if (xx < min)` over 360 candidates
   does not: `plx`/`plz` are chain outputs. A 1-ULP error flips `plwp` by one
   degree when two candidates are near-tied, which shifts
   `nearstar_p_term_start/end` by a degree, which can flip `nightzone`,
   which changes `albedo`, which can change `sctype`. **This is the longest
   float-to-discrete causal chain in the game.**
10. **Ship position `dzat_x/y/z`** -- arbitrary doubles at ~3.8e6 scale;
    24-bit cannot even represent them (ULP 0.25 at that magnitude).

### 3.5 Numeric proof that 24-bit is fatal, at the ship's *starting* position

Computing `nearstar_identity` in IEEE single instead of double, over 2 000
random coordinate triples in the neighbourhood of the default start position
(`dzat_x = +3797120`):

```
max |double - single| = 1.608e-04
the isthere/search_id_code window is 1e-05
```

**The single-precision error is 16× the entire matching window, at the
place the player starts.** No tolerance can be set. This is a direct
measurement, and the real comparison is worse still: the original is 80-bit,
not 53-bit.

---

## 4. Comparisons, indices and shift counts

### 4.1 Branch-selecting comparisons, by severity

The scan produced 365 candidate lines. Classified:

**CRITICAL** (a wrong branch changes the universe):

| site | comparison |
|---|---|
| `NOCTIS-0.CPP:5699`, `5704` | `fcomp sidlow` / `fcomp sidhigh` -- the sensor window (§1.2) |
| `NOCTIS-0.CPP:4022-4023` | `buffer_double[index] > id_low && < id_high` -- the name lookup |
| `NOCTIS-1.CPP:2644`, `2667`, `2683` | the three story-world equalities |
| `NOCTIS-0.CPP:1507` | `if (xx < min)` in `planet_viewpoint` -- the terminator argmin |
| `NOCTIS-1.CPP:3641` | `if (albedo < 25) sctype = OCEAN` -- *integer, therefore safe* (listed so nobody re-flags it) |
| `NOCTIS-1.CPP:3645`, `3646`, `3677`, `1988`, `2004` | the `latitude` tests -- *exact, therefore safe* (§3.1d) |
| `NOCTIS.CPP:1245` | `ap_target_id != ap_target_previd` -- exact double equality; a spurious inequality re-reads the starmap and re-rolls `srand(ap_target_id)` |
| `NOCTIS.CPP:1264` | `current_planet_id != prev_planet_id` -- same shape |
| `NOCTIS.CPP:2842` | `ap_target_id == nearstar_identity` -- exact double equality between two values computed by **the same** formula on the same inputs, so it is safe *provided* both are computed identically. Compute one of them differently and the game never registers arrival. |

**MAJOR** (visible geometry / content):

`NOCTIS-0.CPP:5338`, `5341`, `5343` (`d3 < 250/100/25 × ray` -- LOD gates that
decide whether `surface()` is even called, hence whether the surface seed is
consumed); `:5354` (`d2 < md2`, target acquisition argmin);
`NOCTIS-0.CPP:3069-3073`, `3197-3198`, `3322-3323`, `3559-3560`
(`mag_factor` thresholds selecting `gman2x2`/`3x3`/`4x4` -- the globe
sampling kernel); `NOCTIS-0.CPP:4335-4337` (`q < 2` / `q >= 8` -- integer,
safe); `NOCTIS-1.CPP:1262` (`hpdep < 49152L`); `NOCTIS-1.CPP:3367`
(`nearstar_p_qsortdist[w] < compdist` -- the painter's-algorithm sort, a
tie-flip reorders draw order); `NOCTIS-1.CPP:4168`, `4219`, `3911`
(landing-impact tests: `drop_y > compdist`, `sqrt(dx²+dy²+dz²) < 1600` --
these decide **whether the lander survives**); `NOCTIS.CPP:3223`, `3241`,
`3320`, `3338` (`l_dsd > 0.9999 × initial_d` -- autopilot phase transitions);
`NOCTIS.CPP:2039`, `2072` (`while (dpwr < 15000)` -- the +15000 power bias
loop); `NOCTIS-1.CPP:2037` (`treescaling > 4096` → `mushscaling = 8191`, a
bitmask, so it changes the whole vegetation stream).

**COSMETIC**: the remaining ~300 -- clamps (`if (x > 63) x = 63`), angle
wraps (`if (beta >= 360) beta -= 360`), rasteriser bounds
(`while (yy < yb)`), `fabs(...) < 0.25` dead-zone tests on control input,
palette saturation tests.

Two structural notes on the comparison set:

* `NOCTIS-0.CPP:1864` etc. -- `if (diff < -mindiff || diff > mindiff)` with
  `float mindiff = 0.01` appears **18 times** in the 3-D stick clipper. It is
  a fixed epsilon, so it is robust; do not "improve" it.
* `NOCTIS-0.CPP:1311`, `1319`, `1340` -- `while (f3 > 0.02)` and
  `for (alfa = f2-f3; alfa < f2+f3; alfa += ww)` -- **float loop bounds with a
  float increment**. The trip count depends on rounding. Cosmetic (lens
  flares) but it is the one place where a float difference changes how many
  times a loop runs.

### 4.2 The int16 wrap is the normal path, not a corner case

`zrandom(10 * nearstar_p_orb_seed[n])` (`NOCTIS-0.CPP:4090`, `4091`) narrows
to `int16` at the call boundary. Analytic worst case per star class, using
`class_ray[]`, `class_rayvar[]` and `class_planets[]` from
`NOCTIS-0.CPP:922-931`:

```
cls  ray_max  nop_max   orb_seed_max   10*orb_seed_max   fits int16?
  0     7.0      12          2 581.6          25 816     yes
  1    25.0      18         21 823.1         218 231     NO
  2     0.5       8            758.5           7 585     yes
  3    35.0      15         20 788.4         207 884     NO
  4    20.0      20         21 777.9         217 779     NO
  5     2.0       3             35.0             350     yes
  6     6.0       0             35.0             350     yes
  7     2.5       1            145.0           1 450     yes
  8     9.0       7          1 024.9          10 249     yes
  9    11.5      20         12 521.9         125 219     NO
 10    31.0       2            278.0           2 780     yes
 11     0.3       5             13.2             132     yes
```

**Classes 1, 3, 4 and 9 -- four of the twelve, including the common ones --
overflow `int16` at their outer planets**, by up to 6.7×. The wrap is
therefore load-bearing for planet tilt and orbital tilt on a large fraction
of systems. `class_planets[3] = 15` and `class_planets[4] = class_planets[9]
= 20`, so this is not an exotic tail.

Dead branch worth recording: `nearstar_class == 15` is tested at
`NOCTIS-0.CPP:4105` and `4174`, but `star_classes` is 12, so class 15 never
occurs. Reproduce the branch anyway (it costs nothing) but do not spend
effort validating it.

### 4.3 Float values reaching an array subscript

Only 10 raw hits, and after review the genuine ones are:

| site | subscript | severity |
|---|---|---|
| `NOCTIS-0.CPP:3366`, `3598` | `riga[(int)yy]` -- a `float yy` truncated into the scanline-base table | COSMETIC |
| `NOCTIS-1.CPP:262-265` | `lft_cos[rotation + branchdetail]` where `branchdetail` is a `float` | MAJOR (branch angles of trees) |
| `NOCTIS-1.CPP:302-305` | `lft_cos[rot2]`, `lft_cos[rot3]` where `rot2`/`rot3` are `float` (`rotation + 72`, `+ 36`, wrapped) | MAJOR |

`lft_sin`/`lft_cos` are `float far [361]`. Subscripting with a float
converts via `__ftol` (chop). Because `rot2 = rotation + 72` with `rotation`
itself a float loop counter incremented by the float `branchdetail`, the
index accumulates rounding -- **a genuine float→index hazard, in the tree
generator.**

### 4.4 Float values reaching a shift count

Exactly one, and it is the known one:

```
NOCTIS-0.CPP:2804-2806
    rarity_factor = distance_from_home * 0.25e-8;   // double -> int, chop
    rarity_factor = 1 << rarity_factor;
    rarity_factor--;
```

then `test ax, rarity_factor` in the star loop (`NOCTIS-0.CPP:2858`) decides
whether each sector's star is emitted. **CRITICAL.** `distance_from_home`
maxes near 2e9 so `rarity_factor` stays in 0..5 and the shift is well
defined; there is no UB, only a discrete cliff every 4e9 units.

All the other `>>`/`<<` hits in the scan are shifts of an *already*
converted `long` (`((long)pos_x) >> 14`), which are §2.1 cast sites, not
shift-count sites.

---

## 5. Traps, and three things that turned out not to be traps

### 5.1 `lft_cos`/`lft_sin` are built by accumulation, not by multiplication

```
NOCTIS-0.CPP:3626-3633
    double a = 0, step = M_PI / 180;
    for (c = 0; c <= 360; c++) { lft_cos[c] = cos(a); lft_sin[c] = sin(a); a += step; }
```

`a` drifts from `deg * c`. **Measured: the maximum difference between
`cos(accumulated)` and `cos(deg*c)`, stored as `float`, is 2.84e-14 -- about
five orders of magnitude below a `float` ULP at that magnitude, so it is
invisible in the `float` table.** This is a trap that is *not* a trap: a
port may build the table either way. Recorded so it does not get
re-investigated. (It would matter if the table were `double`. It is not.)

### 5.2 The ship's position is quantised to 24 bits every time you land

```
NOCTIS-1.CPP:3411-3413   float backup_dzat_x = dzat_x; dzat_x = 0;   (and y, z)
NOCTIS-1.CPP:4633-4635 / 5025-5027   dzat_x = backup_dzat_x;         (restore)
```

`dzat_x` is a `double` holding a position of order 3.8e6, where a `float`
ULP is 0.25. **Landing on a planet and taking off again rounds the ship's
parsis position to `float` precision.** This is observable -- it changes the
`frndint` HUD readout and can move `sect_x` across a boundary. It is a
deliberate narrowing in the original and must be preserved, not optimised
away. It is also the reason `dzat_*` cannot simply be "kept in the highest
available precision" by a port.

### 5.3 `random (150 / rainy)` divides by a float that can be small

`NOCTIS-1.CPP:4464`. `rainy` has been through `rainy /= random(4)+1` or
`/= random(3)+2` (`NOCTIS-1.CPP:3650-3655`), so it is not necessarily a
multiple of 0.25 any more. `150 / rainy` is a double, chopped to `int16` at
the call boundary. Guarded by `if (rainy >= 2 || flashes > 5)` at `:4455` and
`if (rainy > 3)` at `:4467`, so division by zero does not occur on the live
path -- but if a port reorders those guards, `rainy == 0` gives `+INF`,
`__ftol(INF)` gives `0x80000000`, low 16 bits `0`, and `random(0)` -- silent,
not a crash.

### 5.4 The HUD datasheet perturbs the shared `fast_random` stream

`NOCTIS.CPP:2996-3005` computes display-only star mass, but on the way it
calls `fast_srand((long)ap_target_x%32000)` and then up to five
`fast_flandom()` draws. `flat_rnd_seed` is a single global
(`NOCTIS-0.CPP:1073`). **Opening the datasheet panel changes the state of the
generator that the renderer and the surface code share.** Every consumer
re-seeds before use, so the coupling is believed harmless -- but it is a real
coupling between UI state and generation state, and any port that lazily
skips the datasheet computation when the panel is closed will diverge.

### 5.5 `globe()`'s parameter is misnamed

Recorded in `PORTPLAN.md` already and re-confirmed here: `globe`'s formal is
`unsigned char far *offsetsmap` (`NOCTIS-0.CPP:3043`) but every call site
passes `n_globes_map` (`NOCTIS.CPP:2588`, `2592`; `NOCTIS-0.CPP:5564`). Not a
float issue; noted because it sits in the same functions as the `fistp`
sites and an implementer reading this registry will be reading that code.

### 5.6 Three things that are *not* quantisation hazards

* **`TDPOLYGS.H` is entirely `float`.** Every declared renderer variable --
  `alfa`, `beta`, `cam_x/y/z`, `dpp`, `x_centro_f`, `opt_*`, `ultima_*`,
  `video_x0..3` -- is a `float`, i.e. 24-bit *storage*. lino's native 24-bit
  floats are a natural match for the renderer's declared types. The
  divergence is only in the intermediates (80-bit on the x87), and the
  registry says those are cosmetic there. **The renderer is the one place
  lino's native floats are close to right rather than badly wrong.**
* **`nearstar_p_orb_seed[n] *= 10` for classes 2/7/15** (`:4106`) does not
  overflow: those classes have small radii and few planets (§4.2).
* **The `0.44444` at `NOCTIS-0.CPP:6235`** looks like a suspicious constant
  but feeds only a compass glyph index. Cosmetic.

---

## 6. Summary -- what an implementation must do

| tier | sites | requirement |
|---|---|---|
| exact integer | §3.1 (a)–(h) | no float at all; watch the C precedence in `%`-chains and the 32-bit wrap |
| small tables | §3.2 | precompute; 360-entry trig and orbit-orientation tables are the big wins |
| one correctly-rounded op | §3.3 | a two-op soft-float suffices; no chain state |
| extended-precision chains | §3.4 | 80-bit engine or a soft-float reproducing 64-bit-mantissa intermediates, **plus the Wave 2 spill transcription** at `NOCTIS-0.CPP:4089` and the `key_radius` loop |
| round-to-nearest converts | §2.4, 37 sites | free under a round-to-nearest policy -- lino `=,` |
| chop converts | §2.1–2.3 | one explicit helper: `__ftol` toward zero, then truncate to the destination width (16 bits for `int`, 32 for `long`, 8 for `unsigned char`) |

**The single highest-value observation in this registry:** the star identity
is a pure function of three exact int32 coordinates through five
correctly-rounded operations, with no accumulated state and no
transcendentals. That is a small, testable, self-contained thing -- and it is
exactly what `STARMAP.BIN`'s 4194/4194 decode already measures. Get that one
function right and §1.1, §1.2 and §1.5's two `srand` sites all fall at once.

**The single most dangerous line** is `NOCTIS-0.CPP:4089`, because the
`(float)` cast sits in the middle of an expression that Borland is free to
keep on the x87 stack, it is upstream of every other planetary parameter, and
no source-level reading can settle where the narrowing lands. It needs the
binary.

---

## 7. Corrections to earlier project documents

| document | claim | measured |
|---|---|---|
| `PORTPLAN.md` | "38 hand-written `fistp` sites" | **37** FP→int stores (36 `fistp` + 1 `fist`), plus 6 `frndint`. Command: `grep -o "fistp" TDPOLYGS.H NOCTIS-*.CPP NOCTIS.CPP \| wc -l` |
| `WAVEPLAN.md` §2 | "`nearstar_identity`, `isthere` window compare -- ~5 correctly-rounded ops on exact integer inputs" | Correct for `nearstar_identity`. `isthere` uses a **different formula** (`×0.00001`, different association) and the two disagree by ~1 ULP, which exceeds the ±1e-5 window beyond ~3.6e8 units/axis -- 26% of rim stars are unreachable in vanilla |
| `WAVEPLAN.md` §2 | "`seedval` products, `global_surface_seed` -- exact required" | Confirmed, and `sctype` (`NOCTIS-1.CPP:3636`) belongs on that list too -- it is CRITICAL and was not previously named |
| `WAVEPLAN.md` §2 | table omits it | `nearstar_p_orb_orient` is one of **360 exact values**; `sctype` selection reduces to a 360-entry table with no float |
| `PORTPLAN.md` | "the known example is `rarity_factor`, where `sqrt` feeds a truncation to `int16`" | The truncation is to `int` (16-bit) and then used as a **shift count**, values 0..5; the `int16` framing is right but the value never approaches the 16-bit limit |

---

*End of registry. Every file:line above was read; every numeric claim was
computed rather than recalled.*
