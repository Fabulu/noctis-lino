# Wave 2 — the two unknowns, settled from the shipped binary

Both questions that gated planetary geometry are answered. Neither could be
answered by reading C source, because both depend on what Borland's compiler
actually emitted; both are now read directly out of `NOCTIS.EXE`.

**UNKNOWN 1 — the type of a `random()` argument. SETTLED: the double does not
survive.** It is chopped by Borland's `__ftol` and narrowed to `int16` at the
call boundary, with a genuine wrap.

**UNKNOWN 2 — operand order in `zrandom`. SETTLED: first draw minus second
draw.** There is no sign flip. The shipped binary agrees with `noctis-iv-lr`.

Everything below is recomputed from the bytes on every test run by three
independent routes. Nothing here is a remembered number: `tests/test_wave2.py`
parses the claims block at the end of this document and fails if any line of it
disagrees with what the routes decode today.

---

## The semantics to port

```
rand()       seed = seed * 0x015A4E35 + 1
             return (seed >> 16) & 0x7FFF          // HIGH word, masked to 15 bits

random(n)    int16 n                                // narrowed by the CALLER
             return (int16)( ((int32)rand() * (int32)n) / 32768 )   // signed, truncating

zrandom(r)   int16 r
             return (float)(int16)( random(r) - random(r) )   // FIRST draw is the minuend
```

and, at every site where the source writes `random(<double expression>)`:

```
int16 arg = (int16)( (int32)( trunc(x) ) )         // chop to 32 bits, then take the LOW 16
```

`noctis-iv-lr`'s `brtl_random((int16_t)(300*nearstar_ray))` and its
`zrandom(range) { return (float)(brtl_random(range) - brtl_random(range)); }`
both match. **Port caveat:** LR's direct `double -> int16_t` cast is undefined
behaviour when the value is out of range, which it routinely is at lines
4090/4091. It happens to agree on x86-64 (`cvttsd2si` to 32 bits, then
truncate), but the lino port must spell the two-step truncation out. Do not
copy the one-step cast.

---

## The evidence chain

### 1. rand is uniquely located

The low half of Borland's multiplier, the bytes `35 4E`, occurs **exactly once**
in the whole 215,744-byte image. It is the immediate of `mov ax,0x4E35`, and the
byte before the function's entry is a `retf`. That fixes rand's body at file
offset **15970** with no guesswork and no remembered address:

```
15970  8b 0e 5c 39     mov cx,[395C]        seed high word
15974  8b 1e 5a 39     mov bx,[395A]        seed low word
15978  ba 5a 01        mov dx,0x015A        multiplier high half
15981  b8 35 4e        mov ax,0x4E35        multiplier low half     <-- the anchor
15984  e8 a6 ff        call <long multiply helper>
15987  05 01 00        add ax,1
15990  83 d2 00        adc dx,0
15993  89 16 5c 39     mov [395C],dx        seed stored as two 16-bit words
15997  a3 5a 39        mov [395A],ax
16000  a1 5c 39        mov ax,[395C]        the HIGH word is the return value
16003  99              cwd
16004  25 ff 7f        and ax,0x7FFF        masked to 15 bits
16007  cb              retf
```

The last four instructions are the reason `random()`'s divisor is `0x8000` and
not something else. Both delivered decoders re-derive rand's *multiply* and
neither checks its *return*, so the suite's own route checks it — mutating the
mask, or returning the low seed word instead, changes the generator completely
and was invisible to the delivered pair.

### 2. rand has exactly ONE caller — so `random()` is not a macro

Borland's `random(num)` is a textual macro, and a macro would inline
`call rand` at every one of the 375 use sites. A raw scan of the image over
both call encodings — `9A off16 seg16` resolved through the load-time segment
arithmetic, and `0E E8 rel16` resolved modulo 2**16 inside the segment frame —
finds **one** call to rand in the entire file. This build compiled `random()`
out of line, which is what forces its argument through a 16-bit stack slot.

### 3. `random` — the answer to UNKNOWN 1

That single caller's function, at file offset **82487**:

```
82487  55                    push bp
82488  8b ec                 mov bp,sp
82490  9a 62 18 00 00        call far 0000:1862   -> 15970 = rand
82495  66 0f bf c0           movsx eax,ax
82499  66 0f bf 56 06        movsx edx,word [bp+6]      <-- the argument is a WORD
82504  66 0f af c2           imul eax,edx
82508  66 bb 00 80 00 00     mov ebx,0x00008000
82514  66 99                 cdq
82516  66 f7 fb              idiv ebx                   <-- SIGNED
82519  5d cb                 pop bp; retf
```

In the far model `[bp+0]` is the saved bp, `[bp+2]` the return offset, `[bp+4]`
the return segment, `[bp+6]` the first argument. The callee reads it with
`0F BF /r`, which takes an `r/m16` source. **Nothing wider can reach it.** The
double is gone before `random` is entered, and the multiply and divide inside
are pure signed 32-bit integer arithmetic with divisor **32768**.

### 4. `__ftol` — how the double gets there

At the disputed line-4089 site the chain is:

```
61545  9b d9 06 8c 10   fld  dword [0x108C]   = 300.0
61550  9b d8 0e 7f 02   fmul dword [0x027F]   = nearstar_ray
61555  9a 65 12 00 00   call far -> 14437 = __ftol
61560  50               push ax               <-- the LOW 16 BITS ONLY
61561  90 / 0e          nop; push cs
61563  e8 b9 51         call -> 82487 = random
```

`__ftol` at **14437** is `fnstcw [bp-2]`, `or byte [bp-1],0x0C` — rounding
control `11`, **truncate toward zero** — `fldcw`, `fistp qword [bp-10]`,
restore the control word, then `mov ax,[bp-10]; mov dx,[bp-8]`, returning a
32-bit long in `dx:ax`. **Only `ax` is pushed.** So the value is chopped, then
truncated again to 16 bits, and only then does `random` see it.

Twelve call sites in the image push a `__ftol` result into `random` or
`zrandom`, all of them the low half. They are the planet and moon generation
sites at NOCTIS-0.CPP lines 4089–4094 and 4195–4199 (plus one at 132098).
No float reaches either function by any other route.

**The wrap is real and load-bearing, not theoretical.** At lines 4090/4091 the
argument is `10*nearstar_p_orb_seed[n]`, and `orb_seed = 3*(n*n+1)*nearstar_ray`
with `nearstar_ray` up to about 35. `10*orb_seed` passes 32767 for roughly
n >= 8 on most star classes, so most planets past index 7 draw their tilt from
a wrapped — often negative — range. A port that keeps the argument wide builds
a different solar system.

### 5. `zrandom` — the answer to UNKNOWN 2

All 36 bytes at file offset **60750**, with nothing omitted:

```
60750  c8 02 00 00   enter 0x0002,0
60754  56            push si
60755  8b 76 06      mov si,[bp+6]        int range
60758  56            push si
60759  90            nop
60760  0e            push cs
60761  e8 db 54      call -> 82487 = random     DRAW 1
60764  59            pop cx                     argument cleanup
60765  50            push ax                    SPILL draw 1
60766  56            push si
60767  90            nop
60768  0e            push cs
60769  e8 d3 54      call -> 82487 = random     DRAW 2
60772  59            pop cx                     argument cleanup
60773  5a            pop dx                     dx <- draw 1
60774  2b d0         sub dx,ax                  dx = draw1 - draw2
60776  89 56 fe      mov word [bp-2],dx         16-bit store
60779  9b            fwait
60780  df 46 fe      fild word [bp-2]           returned in st(0)
60783  5e c9 cb      pop si; leave; retf
```

The `push cs` at 60760 and 60768 is consumed by `random`'s `RETF`, so it is not
a slot the caller can pop; the `pop cx` at 60764 and 60772 removes the pushed
argument. The `pop dx` at 60773 therefore unambiguously recovers the value
pushed at 60765, which is the **first** draw. The subtract at **60774** is
`sub dx,ax`: spilled minus live, i.e. first-executed minus second-executed.

**Write the port as "first draw minus second draw."** Do not write it as a
left-to-right compiler rule. What is observed here is the dataflow of one
compiled function body, and the label "left to right" is an inference on top of
it. Line 4094's `zrandom(p_ray) * (1 + random(1000)/100)` is a different
operator with a different shape and was not decoded by this wave — its draw
order remains open.

The 16-bit store cannot itself wrap: `random(num)` always returns a value with
`num`'s sign and `|value| < |num| <= 32768`, so the difference always fits an
`int16`. LR's promotion to `int` there is harmless.

---

## What a sign flip would have cost, had the answer gone the other way

Traced through every `zrandom` use in NOCTIS-0.CPP (4090, 4091, 4094, 4195,
4196, 4197, 4308, 4310, 4331, 4333):

* **Draw counts are unaffected.** Every conditional that gates a further
  `random()` call keys on constants, planet index, star class or planet type —
  never on a `zrandom` result. Planet count is drawn before any `zrandom`.
  Planet types and counts would have survived; geometry would not.
* Planet tilt and orbital tilt (4090/4091) would be pure sign flips.
* Every planet and moon radius and orbit radius (4307–4315, 4330–4337) would
  shift, and `key_radius` accumulates, so the shift cascades down the system.
* **Not** a pure sign flip for moons: line 4195 puts the result INTO
  `nearstar_p_orb_seed[q]`, which is then the *argument* of 4196–4198, so those
  bodies would get entirely different values rather than negated ones.
* **Not affected at all:** planet orbital eccentricity at 4092, because the
  author wrote `fabs()` around the tilt, absorbing the sign inside the
  argument; and `nearstar_p_ring`, because line 4094's value is dead — 4348
  unconditionally overwrites it for every planet and 4200 zeroes it for every
  moon. Only 4094's three RNG draws matter, not its result.

---

## How this is kept honest

The subject is a 1996 binary that cannot regress, so the regression test guards
the **decoders**, not the file. `tests/test_wave2.py` runs three routes that
share no code:

| route | engine | how it locates anything |
|---|---|---|
| `noctis-harness/ba_w2.py` | capstone | top-down from the unique `35 4E` anchor |
| `noctis-harness/bx_w2.py` | ndisasm | Borland symbol names in DL.EXE/ST.EXE, transferred as masked byte signatures |
| `tests/w2spec.py` | none | named-field byte templates, suffix-anchored backward matching |

and then flips every load-bearing byte in a private copy and requires the
routes to report the changed answer. A decoder that stopped decoding and
replayed a remembered verdict would pass a plain re-read of the binary; it does
not pass the battery. The test proves that by generating exactly such a liar at
run time and requiring the battery to catch it on every mutant.

Three mutants are caught only by the suite's own route, and are recorded as
such rather than asserted of the delivered pair:

* `T_RANDMASK` — rand's `0x7FFF` narrowed to `0x3FFF`
* `T_RANDLOW` — rand returns the low seed word
* `P_FWAITFLOAT` — x87 code planted before an argument push behind an `0x9B`,
  which is where 49 of the 385 call sites hide from both delivered decoders

`Z_CALL_REPOINT` — aiming `zrandom`'s second draw one byte into `random`'s
prologue — is caught by capstone and by the byte-template route, but not by the
signature-transfer route, which wildcards call slots.

---

## Still open — must not be assumed settled

* Line 4094 `zrandom(p_ray) * (1 + random(1000)/100)`: which subexpression
  advances the RNG first. Different operator, different shape, never decoded.
  The result is dead but its three draws are not.
* Whether any of the 49 FWAIT-separated call sites could ever carry a float.
  None does today; only the suite's own route would notice if that changed.

---

<!-- CLAIMS -->
Machine-checked on every run of `tests/test_wave2.py` against all three routes.
Editing a value here without the binary changing fails the suite.

```
layout.header_len                   = 9728
layout.dgroup_file                  = 182144
anchors.rand_entry                  = 15970
anchors.srand_entry                 = 15953
anchors.random_entry                = 82487
anchors.zrandom_entry               = 60750
anchors.zrandom_len                 = 36
anchors.ftol_entry                  = 14437
census.rand.total                   = 1
census.random.total                 = 375
census.zrandom.total                = 10
census.ftol.total                   = 274
selfcheck.anchor_354e_count         = 1
unknown1.verdict                    = NARROWED_AT_CALL_BOUNDARY
unknown1.random_is_macro            = False
unknown1.random_param_width_bits    = 16
unknown1.random_param_signextended  = True
unknown1.random_divisor             = 32768
unknown1.random_div_is_signed       = True
unknown1.random_mul_width_bits      = 32
unknown1.ftol.cw_or_immediate       = 12
unknown1.ftol.rounding              = CHOP
unknown1.ftol.store_width_bits      = 64
unknown1.ftol.return_width_bits     = 32
unknown1.fp_sites_total             = 12
unknown1.nonftol_fp_arg_sites       = []
unknown2.verdict                    = LEFT_TO_RIGHT
unknown2.minuend                    = draw1
unknown2.spilled_draw               = draw1
unknown2.live_draw                  = draw2
unknown2.sub_dst                    = dx
unknown2.sub_src                    = ax
unknown2.sub_file                   = 60774
unknown2.op                         = sub
unknown2.stored_reg                 = dx
unknown2.result_width_bits          = 16
unknown2.return_load                = fild_word
unknown2.call_files                 = [60760, 60768]
randtail.rand_returns               = HIGH_SEED_WORD
randtail.rand_mask                  = 32767
```
<!-- /CLAIMS -->
