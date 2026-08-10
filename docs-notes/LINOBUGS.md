# Bugs and traps found in L.in.oleum

Found while porting Noctis IV to L.in.oleum. Version 1.14 (`releasenumber = 114`),
Win32 package, i386 CPU pack, on Windows 11.

Each entry says what is wrong, how it was established, and what we did -- which
in most cases is **nothing**, because `main/lib/gen/compiler.txt` is under the
WTOF Public License, which forbids modifying it without the author's
authorisation. Where a fix exists it lives in a *copy*, produced by a patch
script, and the shipped file is untouched.

**None of this has been reported upstream yet.**

---

## 1. The command-line parser truncates on `--` anywhere -- and then blames the CPU pack

**Severity: high.** Silent, and it misdirects the diagnosis.

`copy option` (compiler source, around lines 6217–6239) copies an option's value
until it hits either a character below the blank space, or **two consecutive
hyphens** -- with no check that what follows the hyphens is actually an option
name. There is no tokeniser at all; options are located by scanning the whole
command line for `--src:`, `--env:` and so on.

So a path containing `--` silently truncates. Given
`--env:C:\work\my--proj\main`, the environment becomes `C:\work\my`, the derived
pack path becomes `C:\work\my/cpu/i386.bin`, the read fails, and the compiler
reports:

```
internal problem: invalid cpu pack.
```

which points at a file that is perfectly intact. We lost real time to this
before finding it, because the error names the wrong component.

Compounding it: `strstr` finds the *first* occurrence of each option marker
anywhere in the string, so a path containing a literal `--src:` would also be
mis-detected.

**What we did:** our build wrapper refuses any path containing `--` up front,
with a message naming the real cause. Not fixed in the compiler.

**Suggested fix, ~3 lines:** after detecting `--`, require the next character to
be a known option letter and a `:` within a few characters. Self-contained
inside `copy option`. A full tokeniser would be more correct but would break the
routine's deliberate allowance of spaces inside values, which has no quoting
convention to fall back on.

---

## 2. The relative-address modifier in ML fragments is documented backwards, and the sign is inert

**Severity: medium.** Anyone following the manual writes broken jumps.

For `<+N label>` inside a machine-language fragment, the manual states the
compiler computes `label - pc + N`. It computes `label - pc - N`.

The manual's **own worked example** proves the manual wrong: with the program
counter at 103 and the label at 109, the required byte is `05`.
`109 - 103 - 1 = 5`. The documented formula gives 7.

Worse, `+` and `-` reach the same code path and **both subtract**, so the sign
carries no meaning -- `<+4 dLabel>` and `<-4 dLabel>` produce the same address.

Note that subtraction is the *useful* behaviour: an x86 relative displacement is
measured from the end of the instruction, so the digit correctly removes the
bytes following the address field. Shipped example code depends on this.

**What we did: FIXED**, in a patched copy. `+` is left exactly as it is, so
existing code keeps working; `-` now adds, which restores meaning to the sign
without breaking anything. Roughly four lines, branching on the sign character
before the drift is applied.

---

## 3. `linux_compiler.bin` is dead on modern systems

**Severity: high on Linux, none on Windows.**

The shipped Linux compiler segfaults at startup, before parsing arguments, in
every configuration tested -- including with no arguments at all.

Diagnosis, in order:
- It is a dynamically-linked 32-bit ELF needing `/lib/ld-linux.so.2`, absent on
  a modern 64-bit distribution. Installing 32-bit glibc gets past this.
- It then needs 32-bit `libX11.so.6` -- the runtime links X11 unconditionally.
  Installing that gets past this too.
- It then **segfaults immediately**, with no arguments, before any parsing.

The kernel is not the problem (ia32 emulation present). This is a 2004 binary
meeting a 2026 libX11.

**What we did:** abandoned the Linux path and worked on Windows. Not fixed.

The Linux runtime source (`src/linoleum_linux32/`) is GPLv2 and *could* be
rebuilt -- that is the one component of the toolchain that is freely
modifiable -- but it was not needed for this project.

---

## 4. The application-name field is not cleared before it is written

**Severity: cosmetic.** Present in every executable ever produced.

The compiler writes `strlen + 1` bytes over the 40-byte application-name field
in the runtime template, without clearing the remainder. So a program named
`mul64` ships with this embedded in its binary:

```
mul64\0leum runtime
```

-- the tail of the template string `L.in.oleum runtime`, left behind. Verified
by reading the initialisation paragraph of a compiled binary directly.

**What we did:** nothing. Harmless, but every lino executable in existence
carries a shard of the template.

---

## 5. Documentation drift

**Severity: low, but it wastes reverse-engineering time.**

- `readme.htm` states the CPU pack contains **6616** instruction patterns. It
  contains **6241**. The shipped `i386.bin` is 299,576 bytes = `48 × 6241 + 8`,
  and the compiler enforces that equality exactly. The manual's own machine-
  language page agrees with 6241; only the readme is stale.
- The manual calls the program counter `bcodesize`. In the shipped compiler it
  is `bpos`. The manual's description of its behaviour is otherwise accurate.

**What we did:** recorded. Nothing to fix in code.

---

## 6. Traps -- correct behaviour, but surprising enough to cost time

These are not bugs. They are documented (or discoverable) and consistent. They
are listed because each one cost us real debugging.

**Underscores in string literals become spaces.** A filename literal containing
`_` silently writes to a differently-named file. Use the `\us` escape. Our first
probe run looked like a total failure because of this.

**`"variables"` and `"workspace"` are not interchangeable.** In `variables`,
`name = N;` declares a variable initialised to N. In `workspace`, `name = N;`
allocates an *uninitialised vector of N units* and the name becomes its
**address**. So `foo = 0;` in `workspace` allocates nothing, top-of-workspace
never advances, and every symbol silently collapses onto the same cell. No
error, no warning -- just uniformly wrong values. This is documented, but the
two forms look identical and the failure is silent.

**A short read is not an error.** `[Block Size]` is quietly corrected to the
number of bytes actually read, and that correction does not survive the isocall.
Every read needs an explicit check.

**No `SEEK_END`.** `[File Position]` is absolute-from-start only; negatives are
a hard error. Code ported from anything that seeks from the end needs a `TEST`
first to learn the size.

**The current directory is not the executable's directory.** Names go straight
to `open()`. Launch from a shortcut with a different working directory and every
asset load fails.

---

## 7. A language gap, not a bug: no `MUL` analogue of `SPL`

`SPL` (`/%`, `/%'`) exists so a division can yield both quotient and remainder,
because the hardware computes both anyway and discarding one is wasteful.

Multiplication has no equivalent. `MUL.n` and `MUL.i` return only the low 32
bits, so the high half of a 32×32 product is **unreachable from the portable
instruction set** -- even though the CPU pack's own patterns compute it. The
unsigned register-by-register pattern is literally:

```
52  F7 E0  5A        push edx ; mul eax ; pop edx
```

`mul eax` produces the full 64-bit result in `edx:eax`, and the pattern then
discards `edx`.

This matters for anything doing 32-bit fixed-point or hashing. Noctis IV's own
galaxy generator needs exactly this -- it folds `edx` back into `eax` after an
`imul` -- and the original achieved it with hand-encoded 386 opcodes.

**What we did:** two things.

1. A **machine-language fragment** -- `{ F7 EB }` for signed, `{ F7 E3 }` for
   unsigned -- which needs no permission, modifies nothing, and is two bytes.
   This is the route we actually ship on.
2. A **language extension**, `*%` and `*%'`, mirroring `/%` and `/%'`: 242
   patterns appended to a copy of the CPU pack, plus the corresponding table
   entries in a copy of the compiler source. Semantically verified on real
   hardware across every operand configuration, and the patched compiler passes
   a fixpoint test -- it recompiles its own source byte-identically, which
   demonstrates that appending patterns shifted no existing index.

The extension is a **contribution, not a dependency**: a census of the original
game found only two algorithms needing a full 64-bit product, and both work
under the stock toolchain via fragments.

---

## Notes for anyone taking this further

The CPU pack format is not documented anywhere as a spec, but it is simple and
the manual's machine-language page describes the pieces. Fixed 48-byte records
at `index × 48 + 8`, raw target opcodes interleaved with 4-byte ASCII operand
placeholders, terminated by `++`, padded with `87 DB` (`xchg ebx,ebx`). The
pattern index is a running sum over earlier instruction and operand-class
records, which is why **appending** is safe and inserting is not.

No tool to build or edit a CPU pack has ever existed publicly; the author
hand-assembled the patterns. We wrote a generator, which is how 242 new patterns
were produced without hand-writing any.

The compiler validates `alignment × count + 8 == filesize` exactly, so a
mismatched compiler and pack fail loudly rather than miscompiling. That is good
design and it saved us more than once.
