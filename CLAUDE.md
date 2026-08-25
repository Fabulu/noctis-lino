# Project working instructions

## Avoid excessive process

- Prioritize the requested project outcome over meta-work, broad audits, adjacent cleanup, and process narration.
- Keep the active work focused. When the user names a priority such as NIVGEN parity, do not switch to a different docket item unless it directly blocks that priority.
- Make small, coherent, tested commits as soon as they are ready. Do not defer every checkpoint behind unrelated long-running measurements or the entire project docket.
- Run the smallest discriminating test first, then the required acceptance gates once. Do not repeatedly rerun unchanged checks, hashes, status commands, or searches without new evidence.
- Do not start silent monolithic jobs expected to run for hours. Split long measurements into resumable, independently retained chunks with visible progress, and stop jobs that are not producing useful output.
- Add tooling, documentation, provenance, or extra tests only when they directly protect or unblock the current result. Do not turn a bounded fix into a framework project.
- Avoid broad repository searches when scoped paths answer the question. Never search, modify, stage, reset, or delete `.tmp-*` paths or protected user-owned artifacts.
- Use at most one agent for one bounded job at a time, and avoid network/API request bursts.
- Report blockers and failures plainly, but keep working on actionable local steps instead of repeatedly reporting status.

## Cross-platform Lino source boundary

- Every shipping target must compile the same tracked `work/vhgame.txt` / `work/vhnivgen.txt` dependency closure from `work/` and `main/lib`.
- Never add, select, stage, copy over, or generate architecture-specific gameplay, renderer, floating-point, library, or other Lino `.txt` forks. Raw target-machine blocks remain forbidden throughout the shipping closure.
- Platform selection may vary only compiler CPU/SYS packs, code-generator/output-format implementation, and runtime/ABI code below the shared Lino source boundary.
