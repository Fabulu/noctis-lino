# Native FPS measurements

This tracked record is updated whenever a retained native-performance checkpoint is published. It keeps healthy-host absolute measurements, depressed-host ABBA comparisons, rejected experiments, and instrumentation-only evidence separate.

The retrospective tables below record every result recovered for this publication pass from retained raw reports and completed task records. Values marked as task-record summaries are rounded exactly as they were preserved there; no missing precision has been invented.

## Current status

- Goal: sustained full-fidelity **60 Hz** presentation while preserving at least **18.206 Hz** authentic simulation.
- Best retained-lineage healthy-host presentation: **60.15187849720224 Hz**.
- Simulation at that healthy-host record: **18.585131894484412 Hz**.
- The fixed five-second retained-lineage record exceeds 60 Hz by **0.15187849720224267 Hz**.
- Sustained acceptance remains open. The retained lineage held **59.88741964493888 Hz** for 30 seconds and **59.800276745077774 Hz** for 60 seconds on healthy controlled moving-surface runs while preserving **18.252672950737768 Hz** and **18.255172298818 Hz** simulation respectively. The minute run lost about 12 whole presentation periods and recorded a 22.385111828196283-ms maximum lateness, so it does not yet prove hitch-free 60-Hz pacing. Task #224's separate current-production 30-second whole-period screen reached only **49.79336088521531 Hz** at **18.29756032528996-Hz** simulation on a depressed/stalling host and does not supersede the healthy evidence. A rejected pure-Lino zero-timeout-yield experiment materially improved the previously collapsing orbital minute from **48.38468068108054 Hz** to **59.768851585398345 Hz**, but it lost Ordering B presentation by **0.04755192797978358 Hz** and was restored under the binding no-averaging rule.
- Current production shared-Lino floating-point source: `work/fp/fpsoft.txt`, SHA-256 `063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc`.
- Current production executable: `work/vhgame.exe`, 645,966 bytes, SHA-256 `e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0`.
- Current production i386m compiler: `main/lib/gen/compiler114m.exe`, 86,288 bytes, SHA-256 `cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87`.
- Current production CPU pack remains `main/cpu/i386m.bin`, SHA-256 `1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7`.
- Task #187 deferred Task #185's compiler-private C/D/E physical-base demotions from every hot GUI row tail to the final-row fallthrough while preserving shared-Lino operations, workspace traffic, counter traces, branches, terminal registers/flags, and generated layout. Candidate A passed simulation at **18.49217638691323 Hz** and reached an experimental **59.94716521032311 Hz**, but it lost **0.2047132868791337 Hz** and added **219,178.05159074068 cycles/presentation** against Baseline A, so Ordering B and fidelity were skipped and Task #185 production was restored byte-exactly. The unchanged production Baseline A independently established the first fixed-discriminator result above target: **60.15187849720224 Hz** at **18.585131894484412-Hz** simulation and **38,184,297.03654485 cycles/presentation**.
- The first sustained current-production checks used the same private desktop, core 3 / `0xc0`, above-normal priority, and moving-surface checkpoint. Healthy 30- and 60-second runs reached **59.88741964493888 Hz** and **59.800276745077774 Hz**, with **18.252672950737768-Hz** and **18.255172298818-Hz** simulation. A separate 120-second run was depressed before measurement—8.476889099925756-second startup, 55.414247728783515-ms first input-effect delay, and 45,589,125.932019375 cycles/presentation—and reached only **49.93577660266569 Hz** / **18.17438737551504-Hz** simulation. Its terminal current-FPS field was 61 and an immediate capsule health control returned **59.97993981945837 Hz** with zero missed deadlines, so the 120-second aggregate is retained as depressed-host evidence rather than misclassified as a steady-state product result.
- Task #189 tested a fast-only five-ms sleep/spin margin in shared Lino. Candidate A passed simulation at **18.4221065278334 Hz**. Ordering A won **2.24895725210388 Hz** and removed **11,313,811.625547864 cycles/presentation**; Ordering B won **0.73827685112223 Hz** and removed **8,896,737.635609157 cycles/presentation**. Synchronized authoritative fidelity passed and the candidate performed real sleep calls, but Windows sleep overshoot defeated the actual sustained target: orbital reached only **56.68016194331984 Hz** over 60 seconds with 1,199 misses. The short ABBA win was therefore not retained, and the accepted source/executable were restored.
- Task #190 then tested one zero-timeout scheduler yield before the unchanged fast deadline spin. It avoided coarse sleeping and raised the sustained orbital minute to **59.768851585398345 Hz** at **18.202104982680524-Hz** simulation, versus current production's prior depressed **48.38468068108054 Hz** result. Strict ABBA still rejected it without averaging: Ordering A won **9.411931695155181 Hz** and removed **7,026,097.853791609 cycles/presentation**, while Ordering B lost **0.04755192797978358 Hz** despite removing **257,407.3969855383 cycles/presentation**. Fidelity was skipped after that mandatory presentation reversal, and production was restored byte-exactly. Simulation-frame-only, inline-wait, and pre-presentation placements were screened separately and failed to match the simple post-publication yield's sustained result.
- Task #195 tested a two-pass fixed-2x shared-Lino publisher that wrote the completed RGB page directly to Backdrop and Primary, then combined it with Task #190's strongest post-publication zero-timeout yield. The model proved identical 640x400 products and 192,000 fewer 32-bit reads per presentation; generated-code evidence proved the existing exact 210-byte i386m fixed-scaler lowering remained active with no scalar fallback. Candidate A passed simulation at **18.488745980707396 Hz**; Ordering A won **1.4121838880681281 Hz** and removed **945,355.109020114 cycles/presentation**. Ordering B reversed both mandatory metrics, losing **1.769835658117458 Hz** and adding **1,065,525.5832088962 cycles/presentation**. The orderings were not averaged, fidelity and sustained orbital were skipped, and production was restored byte-exactly.
- Task #196 reduced scheduler fairness to one post-publication `Sleep(0)` on alternate fast presentations. Its five-second capsule screen reached **60.16 Hz**, but the orbital minute collapsed to **52.56756306441401 Hz** at **18.211203305674964-Hz** simulation with **1,300 / 3,155** missed deadlines. ABBA and fidelity were skipped after the sustained failure, and production was restored byte-exactly.
- Task #197 raised scheduler fairness to three `Sleep(0)` yields per four fast presentations. Its orbital minute improved to **59.27482571133127 Hz** at **18.212748924246974-Hz** simulation, but remained below the established **59.7-Hz** sustained screen with **1,142 / 3,554** missed deadlines. ABBA and fidelity were skipped, and production was restored byte-exactly.
- Task #198 restored every-presentation yielding while hoisting the zero-timeout store to startup and fast-mode re-entry. The model proved the retained 16-ms margin makes the nonzero timed-sleep assignment unreachable during the exact **16.666666107936592-ms** fast period, and the orbital profile independently recorded zero timed sleeps. A healthy five-second capsule reached **59.91 Hz**, but the orbital minute reached only **58.1693470515766 Hz** and its **18.163353644324577-Hz** simulation missed the binding floor. ABBA and fidelity were skipped, and production was restored byte-exactly.
- Task #199 combined every-presentation yielding with a baseline-i386 `LODSD`/`STOSD` exact fixed-2x scaler. The model preserved all **64,000** source loads, **256,000** ordered destination stores, terminal workspace/register/flag state, and the common shared-Lino source; compiler self-host fixpoint and exact lowering also passed. On a depressed host, Ordering A won **5.883586587470077 Hz** and removed **5,262,981.549778044 cycles/presentation**, but Ordering B reversed both metrics, losing **6.477423830722088 Hz** and adding **5,859,684.450868554 cycles/presentation**. The orderings were not averaged, sustained orbital and fidelity were skipped, and production was restored byte-exactly.
- Task #200 modeled and built a shared-Lino adaptive yield that calls `Sleep(0)` only with at least two whole milliseconds of deadline residual. Its first health screen launched in **10.146581599954516 seconds** and reached only **48.68448311580692 Hz**, while authentic simulation remained **18.85228920654651 Hz**. That depressed-host screen did not admit a sustained or ABBA candidate conclusion; the candidate is preserved as deferred evidence and production was restored byte-exactly.
- Task #201 traced the selected Win32 SYS-pack runtime and proved that Lino `SLEEP` is already a direct `kernel32!Sleep([Sleep Timeout])` call. `Sleep(0)` therefore has native Windows scheduler-yield semantics; introducing a higher-resolution timed wait would require changing the native SYS-pack runtime/import surface, so no runtime candidate was activated.
- Task #202 tested the least-invasive shared-Lino scheduling alternative, `thread priority = 3`, whose generated executable differed only in the one-byte `LNLMInit` priority director. Candidate A preserved **18.708509354254677-Hz** simulation, but on the same depressed host it lost **4.478013293428411 Hz** and added **4,171,403.2481553406 cycles/presentation** against Baseline A. Ordering B, sustained orbital, and fidelity were skipped under the binding rejection rule, and production was restored byte-exactly.
- Task #203 instead favored the GUI/runtime threads with shared-Lino `thread priority = 1`; the generated executable again differed only in the one-byte `LNLMInit` director. On a healthy host Candidate A reached **59.73715651135006 Hz** at **18.51851851851852-Hz** simulation, but Baseline A reached **59.987881236113914 Hz** and also used **39,124.00801347196 fewer cycles/presentation**. The candidate lost both mandatory Ordering-A metrics, so later gates were skipped and production was restored byte-exactly.
- Task #204 used that 59.988-Hz healthy production control to start one unchanged 60-second orbital recheck. The run subsequently collapsed to **28.43846949327818 Hz** at **18.264002401841413-Hz** simulation and **80,582,071.83049853 cycles/presentation**; its immediate capsule control remained depressed at **56.08040201005025 Hz**. This is retained as depressed-host evidence with no sustained acceptance conclusion and no production change.
- Task #205 modeled and built two consecutive post-publication shared-Lino `Sleep(0)` yields followed by the unchanged exact deadline spin. Its only health screen launched in **8.669907599920407 seconds** and reached **52.50354753699574 Hz** at **18.85262517737685-Hz** simulation and **43,552,292.185328186 cycles/presentation**. Because the host was already independently depressed, ABBA, sustained orbital, and fidelity were deferred without a candidate conclusion; production was restored byte-exactly.
- Task #206 attributed the fixed orbital checkpoint on a depressed host without admitting a candidate-FPS conclusion. Direct instrumentation measured **0 ms/presentation** in `VHT render`, proving that branch is skipped, while the active `VHG local render` cost **10.764073345590855 ms/presentation** in its isolated run. Broader partitions measured star/setup at **8.1441168191003 ms**, other bodies at **5.839501542435134 ms**, and the selected body at **0.06521998808820742 ms**; the narrowed star/setup run identified selected-origin/resident scanning as the largest isolated subphase at **4.8364453509384 ms** (about **68.5%** of the measured star/setup partition). The next exact shared-Lino candidate is squared-distance comparison only inside resident selection, retaining square-root distance everywhere rendering or LOD consumes it. Accepted production was restored byte-exactly.
- Task #207 used finite squared distances only to reject generated bodies that could not enter the rooted resident top two. Rooted fallbacks preserved rounded-root collisions, stable ties, NaN/infinity behavior, the final public distance, and the moon-primary rescan; a **579,195-case** model proved identical resident indices. Candidate A passed authentic simulation at **18.6084142394822 Hz** and reached **60.07281553398058 Hz**, but Baseline A reached **60.08328375966686 Hz** with **303,493.9966329932 fewer cycles/presentation**. Both mandatory Ordering-A metrics therefore lost; Ordering B and fidelity were skipped, and accepted production was restored byte-exactly.
- Task #209 replayed the resident scan's exact raw body-relative coordinates and rooted distance for each later non-selected body while the integral UTC-second epoch remained unchanged. A **4,092-case** model preserved raw signed-zero/NaN/infinity payloads, type-10 distance state, epoch-change fallback, coordinate PGF slots, selected-body behavior, and common shared-Lino source boundaries. On a depressed and sharply variable controlled host, Ordering A won **1.9691200809515195 Hz** and removed **1,310,924.2336182296 cycles/presentation**, but Ordering B reversed both mandatory metrics, losing **14.980034450360165 Hz** and adding **13,067,228.48687476 cycles/presentation**. The contradictory orderings were not averaged; fidelity was skipped and accepted production was restored byte-exactly.
- Task #210 modeled a same-second cache of exact absolute body vectors. An initial overlapping-stride draft was discarded, and a six-unit version that won preliminary ABBA and public-fidelity gates was also discarded after semantic review found that it omitted frame-terminal `VHGNDowny0/1`. The final eight-unit version cached those words too; its flat **640-unit**, **12,304-case** model preserved all six vector words, both terminal down-y words, moving-camera subtraction, rooted distance, epoch rollover, lifecycle invalidation, and the 80-body bound. On a severely depressed and variable controlled host, Ordering A won **6.71608747461276 Hz** and removed **15,267,965.410845146 cycles/presentation**, but Candidate B fell to **18.0986061992927-Hz** simulation and Ordering B reversed both metrics, losing **6.895873987449285 Hz** and adding **16,431,498.766233765 cycles/presentation**. The candidate was rejected without averaging, synchronized fidelity and sustained profiling were skipped, and accepted production was restored byte-exactly.
- Task #212 kept Task #210's exact eight-word cold records but replayed only the six public vector words per hot hit, retained the latest skipped body in one private pending field, and restored `VHGNDowny0/1` once at common render exit instead of on all **167** modeled hot hits. Its corrected **12,304-case** flat-workspace model and adversarial semantic review preserved moving-camera geometry, epoch/lifecycle failure, type-10 companions, surface hits/misses, RNG/painter order, and strict terminal state. The review caught and removed two false surface-miss invalidations before timing; the corrected private build had **62 warnings, 0 errors**. Candidate A reached **31.978543428925107 Hz** and **68,267,842.58064516 cycles/presentation**, but its **18.155560140292966-Hz** simulation missed the binding floor by **0.05043985970703346 Hz**. Baseline A, reverse ordering, fidelity, and sustained profiling were therefore skipped immediately, and accepted production was restored byte-exactly.
- Task #214 tested a two-level exact orbital cache: same-second selected-relative basis and absolute/orbit scratch plus current-presentation camera-relative geometry and strict helper-terminal replay. An initial unmeasured 16-word draft was discarded after adversarial review found missing FP/VHGND helper state; the corrected 64-word record uses 42 words, passed a **12,304-case** strict-state model and bounded semantic audit, and built privately with **62 warnings, 0 errors**. Ordering A won **2.7579903014523452 Hz** and removed **2,614,461.1106627285 cycles/presentation**; Candidate A reached an experimental **51.09635888151277 Hz** at **18.708509354254677-Hz** simulation. Ordering B reversed sharply: Candidate B lost **8.067775748107586 Hz**, added **12,132,844.321157992 cycles/presentation**, and reached only **18.014329580348004-Hz** simulation, missing the binding floor by **0.19167041965199516 Hz**. The contradictory orderings were not averaged, synchronized fidelity and sustained profiling were skipped, and accepted production was restored byte-exactly.
- Task #215 folded nearest-primary selection into the mandatory all-body resident scan, then replayed only the final source-order primary and unchanged trailing owner checks when a moon was nearest. Its **3,572-case** exact-transform model and two bounded semantic audits preserved stable ties/unordered values, raw distances, map selection, planar-distance `FSW0`, FP/VHGND scratch, and terminal A-E state; the private shared-Lino build had **62 warnings, 0 errors**. Candidate A narrowly passed simulation at **18.21158174749335 Hz**, but on a severely depressed controlled host it reached **33.35379578473501 Hz** versus Baseline A's **34.32356483340024 Hz**, losing **0.9697690486652277 Hz** and adding **640,299.9062533602 cycles/presentation**. Ordering B, synchronized fidelity, and sustained profiling were skipped immediately, and accepted production was restored byte-exactly.
- Task #216 cached only the static pre-time orbital-rate root for each in-range local body while retaining the exact live-seconds suffix and original body-vector statement stream. Its **3,825-case** exact-transform model covered **3,600** cold misses, **3,600** hot hits, **450** fallbacks, all **80** invalidation records, primary/moon `FS0`, FP/VHGND scratch, and terminal A-E state; the private shared-Lino build had **62 warnings, 0 errors**. Candidate A reached **32.19814241486068 Hz** and **69,809,969.87820514 cycles/presentation**, but simulation was only **18.163054695562437 Hz**, missing the binding floor by **0.042945304437562726 Hz**. Every baseline, ordering, fidelity, and sustained stage was skipped immediately, and accepted production was restored byte-exactly.
- Task #217 replaced eleven fixed local-renderer `IntToF` calls with their exact widened-binary32 raw binary64 words while retaining each explicit `FI` assignment. Its exact-transform model proved all six constants, **896** visible-state cases, `FS0`, A-E, the same next multiply, private conversion scratch, and the common shared-Lino boundary; the private build had **62 warnings, 0 errors**. Candidate A passed simulation at **18.988648090815275 Hz**, but reached **55.72755417956656 Hz** versus Baseline A's **55.90312815338042 Hz**, losing **0.17557397381386153 Hz** and adding **269,892.5106431395 cycles/presentation**. Ordering B, synchronized fidelity, and sustained profiling were skipped immediately, and accepted production was restored byte-exactly.
- Task #218 preserved one five-byte call at each of those eleven sites and redirected it to one of six EOF-appended exact fixed-F64 helpers. The **1,408-case** visible-state model and generated-layout proof passed: all pre-existing instruction addresses and bytes were exact except the eleven call displacements, and the six helpers added **156 bytes** after unreachable padding. All four simulation gates passed. Ordering A won by **9.437659529495733 Hz** and removed **11,247,870.869277269 cycles/presentation**, but Ordering B reversed both metrics, losing **7.1132487953484045 Hz** and adding **10,139,391.97071679 cycles/presentation**. The contradictory orderings were not averaged; fidelity and sustained profiling were skipped, and accepted production was restored byte-exactly.
- Task #219 removed ten provably dead fixed local-renderer `FI` stores, general conversions, and FA-to-FB copies by loading their exact binary64 FB words directly; the ring-radius `FI=5` store was retained with one exact EOF-appended helper because it can escape as terminal state. The **1,408-case** visible-state model and normalized **93,514-instruction** generated-layout proof passed with zero unexplained non-control changes, no branch into a replacement interior, a byte-exact shifted package suffix, and a net **164-byte** executable reduction. Candidate A passed simulation at **18.852787805856398 Hz**, but reached **36.50220617729643 Hz** versus Baseline A's **38.91977760127085 Hz**, losing **2.4175714239744224 Hz** and adding **3,469,374.3296703324 cycles/presentation**. Ordering B, synchronized fidelity, and sustained profiling were skipped immediately, and accepted production was restored byte-exactly.
- Task #220 replaced the six ordinary/selected local-renderer fixed 25/100/250 `IntToF` plus portable `FMul` gate sequences with shared-Lino direct p64-then-p53 scalar multiplies. The corrected **197,358-product**, **592,074-branch**, **1,536-visible-state** model covered the signed `NsZRandom(100)` radius bound of **0.0027270000000000003** through **17.94**, and the generated-layout proof confined all **330** changed byte values to six exact 68-byte islands. Candidate A passed simulation at **18.552127445049404 Hz** and Ordering A won **5.424869784321466 Hz** while removing **4,141,269.3106844276 cycles/presentation**. Ordering B reversed both mandatory metrics: Candidate B reached **45.73972879983809 Hz** versus Baseline B's **52.36857885268839 Hz**, losing **6.6288500528502965 Hz** and adding **5,937,019.075525232 cycles/presentation**. The contradictory orderings were not averaged; synchronized fidelity and sustained profiling were skipped, and accepted production was restored byte-exactly.
- Task #224 buffered one 32-bit radicand limb in direct shared-Lino scratch and moved dynamic source-pointer access out of the 64-step restoring loop into three cold boundary handoffs. The exact model reduced radicand shifts from **256** to **64** and proved zero hot dynamic pointer reads while preserving the accepted private residual, p64/p53 output, terminal public state, and every source limb at zero. Ordering A won **1.198251818017276 Hz** and removed **916,678.2864291072 cycles/presentation**; Ordering B won **1.3580240875864789 Hz** and removed **795,384.8072732016 cycles/presentation**. Both candidate arms exceeded the authentic simulation floor, synchronized authoritative fidelity passed, and the candidate is retained. Its separate depressed/stalling-host 30-second screen reached **49.79336088521531 Hz** at **18.29756032528996-Hz** simulation, so the healthy absolute record and open sustained-acceptance status are unchanged.
- Task #226 retained Task #224's buffered radicand schedule but carried the exact odd trial state `T=2*q+1` in C:D, eliminating **448 hot root-word reads**, **128 hot root-word writes**, **192 shifts**, and **128 ORs** per positive root before one final decode. The **65,548-case** normalized model, **92,146-case** binary64 pipeline, bounded adversarial review, and exact generated-code/layout proof passed after removing a tautological state check and adding explicit remainder/comparison/borrow verification. Candidate A preserved simulation at **18.75637104994903 Hz**, but reached **53.00713557594292 Hz** versus Baseline A's **56.45645645645646 Hz**, losing **3.4493208805135396 Hz** and adding **2,806,887.349945441 cycles/presentation**. Ordering B, fidelity, and sustained screening were skipped, and Task #224 production was restored byte-exactly.
- Task #222 replaced the shared-Lino public square-root helper's **65 `Mul128` calls** with one exact **64-iteration restoring root**, reproduced the accepted private residual equality-borrow behavior, and used 20 unreachable shared-Lino bytes to preserve every downstream generated address. The semantic model, exact production-layout proof, and synchronized authoritative fidelity all passed. Ordering A won **4.516166667722868 Hz** and removed **3,498,897.0531333983 cycles/presentation**; Ordering B won **1.7667213544580909 Hz** and removed **1,506,797.381630063 cycles/presentation**. Both candidate arms exceeded the 18.206-Hz simulation floor, so the candidate was retained and now serves as Task #224's accepted baseline. The controlled variable/depressed-host ABBA does not replace the **60.15187849720224-Hz** healthy absolute record, and its separate **50.60040026684457-Hz** 30-second screen did not close sustained acceptance.
- Task #185 retained counter-preserving memory-source comparisons in Task #180's two fail-closed GUI islands while leaving every shared-Lino byte and operation unchanged. Ordering A won **1.9097471853053918 Hz** and removed **1,345,049.8325586468 cycles/presentation**; Ordering B won **1.6400813543026374 Hz** and removed **834,817.0615155473 cycles/presentation**. Both candidate arms exceeded 18.206-Hz simulation and synchronized authoritative fidelity passed. Candidate B reached 59.50446791226645 Hz on this controlled near-record/variable-host run, so the healthy absolute record remains unchanged.
- Task #186's single fixed-discriminator production recheck reached **59.43985492645577 Hz** at **18.537175095708243-Hz** simulation and **38,646,174.55932204 cycles/presentation**. It is a controlled near-record observation **0.36683053467994853 Hz** below the existing healthy absolute record, which remains unchanged.
- Task #180 retained two fail-closed i386m physical-base/block-index lowerings for the unchanged shared compose and fixed-2x Lino operations. Ordering A won **10.234100760894577 Hz** and removed **11,571,455.772213116 cycles/presentation**; Ordering B won **11.119072658700318 Hz** and removed **13,254,397.755512588 cycles/presentation**. Both candidate arms exceeded 18.206-Hz simulation and synchronized authoritative fidelity passed. This controlled depressed/variable-host retention does not replace the healthy absolute record.
- Task #183 preserved every GUI counter write but tested each retained Task #180 loop against its live block index instead of reloading the counter. Candidate A passed simulation by only **0.023694146242657865 Hz**, then lost **3.603972684157135 Hz** and added **5,228,006.329734832 cycles/presentation** against Baseline A. Ordering B and fidelity were skipped, and Task #180 production was restored byte-exactly.
- Task #167's exact scalar delta-pointer layer copy remains active inside Task #185's compiler. Its original isolated ABBA checkpoint won presentation by 1.600824228101473 Hz and 2.55783980794763 Hz while removing 2,727,557.8689971715 and 3,737,071.677122414 cycles/presentation across the two depressed-host orderings, then passed synchronized authoritative fidelity.
- Task #169 folded four exact marked palette-address additions into i386m palette-load displacements while leaving the shared-Lino scalar operations intact. Ordering A won by **12.383072276707573 Hz** and removed **15,041,694.753770493 cycles/presentation**, but Ordering B reversed, losing **7.354369904772071 Hz** and adding **9,963,375.42605704 cycles/presentation**. The contradictory orderings were not averaged; synchronized fidelity was skipped and Task #167 production was restored byte-exactly.
- Task #171 fused the two exact marked GUI counter tails from `DEC memory; reload; CMP 0; JNE` to `DEC memory; JNE`, preserving all 32,000 counter writes and both island endpoints. Candidate A passed simulation at **18.852787805856398 Hz**, but lost **8.767020116546654 Hz** and added **7,379,992.754345141 cycles/presentation** against Baseline A. Ordering B and fidelity were skipped, and Task #167 production was restored byte-exactly.
- Task #173 replaced the exact marked Task #167 layer-copy body with a near-jump to a compiler-owned four-dword appendix while leaving the shared scalar Lino loop unchanged. Candidate A passed simulation at **18.86035313001605 Hz**, but lost **11.876222535595687 Hz** and added **12,659,944.07336431 cycles/presentation** against Baseline A. Ordering B and fidelity were skipped, and Task #167 production was restored byte-exactly.
- Task #175 kept the same 23-byte marked scalar-copy island and moved one state-neutral LEA from the hot preheader to the cold row exit so the short-backedge loop fits one aligned fetch block. Ordering A won by **2.711009346717532 Hz** and removed **5,859,078.885536723 cycles/presentation**, but Ordering B lost **1.07469156653638 Hz** and added **1,916,360.4575268775 cycles/presentation**. The contradictory orderings were not averaged; fidelity was skipped and Task #167 production was restored byte-exactly.
- Task #177 replaced only the same marked 23-byte i386m island with an end-pointer/negative-index scalar loop while leaving the shared Lino loop unchanged. Candidate A reached **35.044320758606474 Hz**, but simulation was **18.140589569160998 Hz**, missing the binding gate by **0.06541043083900178 Hz**. All comparison and fidelity stages were skipped, and Task #167 production was restored byte-exactly.
- Task #153 reversed each terrain replay command to destination-high/value-low fields and added an exact adjacent i386m `C = D; C & 65535` fold to `MOVZX ECX,DX`, removing one dynamically executed extraction instruction at each of three replay decoders. It won presentation by 0.5138524590503692 Hz and 0.4558171701612608 Hz while removing 481,125.0108108148 and 1,784,514.336641848 cycles/presentation across the two depressed-host orderings, then passed synchronized authoritative fidelity. The shared Lino closure remains common to every shipping target; the optimization is retained without replacing the healthy absolute record.
- Task #149 generalized exact i386m register `& 65535` lowering across all 322 generated A/EAX, B/EBX, C/ECX, and D/EDX sites, with E/ESI support covered by the focused fixture. It won presentation by 2.7516803584764773 Hz and 1.5337899900937515 Hz while removing 3,204,463.332275696 and 2,107,022.1561563835 cycles/presentation across the two depressed-host orderings, then passed synchronized authoritative fidelity. The shared Lino source is unchanged; this target-code-generator checkpoint is retained without replacing the healthy absolute record.
- Task #145 replaced the paired culling replay's repeated command-base construction with one exact shared-Lino indexed command load. It won presentation by 5.550831977811946 Hz and 8.926258786655339 Hz while removing 8,233,763.470827088 and 12,123,875.996125333 cycles/presentation across the two depressed-host orderings, then passed synchronized authoritative fidelity. It is retained without replacing the healthy absolute record.
- Task #140 folded the second paired culling-replay destination into its exact shared-Lino store displacement and removed the hot cursor increment. It won both mandatory metrics in both depressed-host ABBA orderings and passed synchronized authoritative fidelity, so it is retained without replacing the healthy absolute record.
- Task #127's shared-Lino culling-pair replay won both mandatory metrics in both ABBA orderings and passed synchronized authoritative renderer/gameplay fidelity. Its variable-host Candidate B reached 57.23498589278517 Hz at 18.540910923014913-Hz simulation, so it is retained as a relative optimization without replacing the healthy absolute record.
- Task #125's Candidate B supplied the retained-lineage healthy absolute record and reported an internal current-FPS field of 60; the fixed five-second external rate remains the binding **59.80668546113572 Hz** observation.
- The rejected indexed-replay Candidate A reached **58.859223300970875 Hz**, but lost both required Ordering-A metrics to the accepted baseline and was restored.
- Task #121's exact marked replay LEA was rejected on a depressed host after Candidate A preserved simulation but fell to **45.85286325657224 Hz** versus **55.47652916073969 Hz** for Baseline A and added **8,694,755.280439556 cycles/presentation**. This comparison does not replace the healthy absolute record.
- Task #123's aligned unchanged replay loop won Ordering A but reversed sharply in Ordering B, losing **13.453520196099156 Hz** and adding **10,898,005.981137909 cycles/presentation**. The candidate was rejected and restored; its Baseline B independently supplied the previous 59.441973311767086-Hz healthy production observation.
- Task #129's fixed-offset culling-scratch replay also reversed after winning Ordering A: Ordering B lost **6.731333731254345 Hz** and added **8,276,088.460966222 cycles/presentation**. Fidelity was skipped and Task #127 was restored exactly.
- Task #131's fixed three-point projected terrain-bounds unrolling passed Candidate A's simulation gate at **18.208152286364577 Hz**, but Ordering A lost **3.54358616920441 Hz** and added **6,741,130.921997875 cycles/presentation**. Reverse ordering and fidelity were skipped, and Task #127 was restored exactly.
- Task #135 generalized the exact nine-byte i386m immediate-multiply lowering across 422 production instruction islands while leaving rejected constants 18 and 320 untouched. Candidate A preserved simulation at **18.996489779062564 Hz**, but Ordering A lost **5.111591595534634 Hz** and added **7,305,500.213919416 cycles/presentation**. Reverse ordering and fidelity were skipped, and Task #127 was restored exactly.
- Task #138 combined the paired culling-replay cursor increments in shared Lino. Candidate A reached an experimental **59.895833333333336 Hz** at **18.42948717948718-Hz** simulation and beat Baseline A by **0.36260548523206637 Hz**, but added **112,786.33152590692 cycles/presentation**. The mandatory metrics therefore contradicted; reverse ordering and fidelity were skipped, and Task #127 was restored exactly.
- Task #147 specialized all 12 exact i386m `D & 65535` sites from six-byte `AND EDX,0x0000FFFF` to three-byte `MOVZX EDX,DX`. Compiler self-host fixpoint, representative exact outputs, flag liveness, and every production layout/packaging difference passed, but Candidate A lost **0.23924762128802968 Hz** and added **445,485.7919146791 cycles/presentation**. Reverse ordering and fidelity were skipped, and the Task #145 compiler and production executable were restored exactly.
- Task #151 specialized 1,681 eligible register-only i386m ADD/SUB/AND/OR/XOR immediate forms to exact signed-byte encodings, saving 3,847 generated bytes and 3,848 aligned executable bytes. Compiler self-host fixpoint, 150-case edge semantics, and every production instruction/offset/layout difference passed, but Candidate A fell to **38.57201477226098 Hz** versus **56.88924752874723 Hz** for Baseline A and added **18,989,422.96631205 cycles/presentation**. Reverse ordering and fidelity were skipped, and the Task #149 compiler and production executable were restored exactly.
- Task #155 folded 16 exact adjacent i386m byte loads plus `& 255` masks to memory-source `MOVZX` instructions, saving 80 executable bytes while preserving the shared Lino source. Compiler fixpoint, focused runtime semantics, all production substitutions and relocations, package layout, and removed-flag liveness passed, but Candidate A fell to **54.989816700611 Hz** versus **58.62412761714855 Hz** for Baseline A and added **2,621,398.5306878313 cycles/presentation**. Reverse ordering and synchronized fidelity were skipped by the binding Ordering-A rejection, and the Task #153 compiler and production executable were restored byte-exactly.
- Task #157 compacted each shared-Lino culling replay pair from two physical stream words to one while preserving both logical ordered stores, exact terminal-state placement, executable size, and all code outside four proved islands. The exhaustive stream/encoding model and generated-layout proof passed, and Candidate A preserved simulation at **18.499899457068167 Hz**, but fell to **39.21174341443796 Hz** versus **48.55144855144855 Hz** for Baseline A and added **11,362,552.519848049 cycles/presentation**. Ordering B and synchronized fidelity were skipped by the binding Ordering-A rejection, and Task #153 production was restored byte-exactly.
- Task #159 moved the two shared-Lino repeating recorder backedges before their existing dead D-only footprint padding, removing five ordinary and six culling instructions from the dynamic backedges without changing executable size or semantic operations. Ordering A won by **2.8269448415291265 Hz** and removed **4,255,036.707779884 cycles/presentation**, but Ordering B reversed sharply, losing **8.04067432483346 Hz** and adding **9,535,073.864391401 cycles/presentation**. The contradictory orderings were not averaged; synchronized fidelity was skipped and Task #153 production was restored byte-exactly.
- Task #161 retained every shared-Lino `PGtrval` publication but formed the two repeating recorder commands from live registers and read `PGtrused` once, removing two semantic instructions and two memory reads per producer while preserving exact ordered state stores and executable layout. The exhaustive model and two-island disassembly proof passed, but Candidate A fell to **39.25455987311658 Hz** versus **40.4659717964439 Hz** for Baseline A and added **1,751,079.4141414165 cycles/presentation**. Ordering B and synchronized fidelity were skipped by the binding Ordering-A rejection, and Task #153 production was restored byte-exactly.
- Task #163 mirrored the always-run palette-compose and fixed-2x presenter counters in B while preserving all **32,400 `VHGUIx` stores**, **64,000 compose stores**, and **256,000 Backdrop stores** in exact order. The complete trace model and two-island disassembly/layout proof passed, removing 64,000 counter-memory reads and a net 31,600 generated instructions per presentation, but Candidate A simulation was only **18.132555231346394 Hz**, **0.07344476865360505 Hz** below the binding gate. Baseline A, Ordering B, and synchronized fidelity were therefore not admitted, and Task #153 production was restored byte-exactly.
- Task #165 replaced one exact marked 23-byte i386m scalar L2L row-copy body with a same-size `REP MOVSD` sequence while preserving overlap behavior, ordered stores, executable layout, and the incoming direction flag. Compiler fixpoint, focused positive/negative fixtures, the semantic model, and production layout all passed, and Candidate A preserved simulation at **18.810059292578206 Hz**, but fell to **39.25577591494582 Hz** versus **55.645161290322584 Hz** for Baseline A and added **16,980,524.350543477 cycles/presentation**. Ordering B and synchronized fidelity were skipped by the binding Ordering-A rejection, and Task #153 production was restored byte-exactly.

## Evidence classes

- **Healthy-host absolute:** an absolute production observation on a responsive host. This class establishes progress toward 60 Hz.
- **Depressed-host ABBA:** same-host candidate/baseline discrimination. This class can retain a relative optimization but must not replace a healthy absolute result.
- **Experimental peak:** an unretained candidate observation. It is never reported as production performance.
- **Simulation-gate failure:** Candidate A was below 18.206 Hz, so baseline, reverse ordering, and fidelity were not admitted.
- **Layout/model/attribution only:** no candidate FPS conclusion was admitted.

## Fixed discriminator

Unless a row says otherwise, controlled capsule measurements use:

- checkpoint clock `1344638527`;
- five-second measurement;
- last physical core (physical core 3, affinity `0xc0` on the recorded host);
- above-normal process priority;
- private inactive desktop;
- native executable built from the shared tracked Lino closure;
- 320x200 indexed full-fidelity rendering and authentic 18.206-Hz simulation.

Candidates run in Candidate A / Baseline A / Baseline B / Candidate B order. Candidate A must first preserve 18.206-Hz simulation. A candidate is retained only if both orderings win presentation throughput and process cycles per presentation, followed by synchronized fidelity.

## Retained healthy-host absolute milestones

| Checkpoint | Executable SHA-256 | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation | Evidence |
|---|---|---:|---:|---:|---:|---:|---:|---|
| Packed-threshold Baseline A, then-record | `24d398fc2cd7b8c81222689f6f5c1e9edf886d4771532e379592b661ac8b38b2` | 54.973821989528794 Hz | 18.525976641159886 Hz | 15.071525993902453 ms | 11.76056728760782 ms | 0.8487283214656896 ms | 41,751,507.307692304 | `build/packed-depth-threshold-20260828/baseline-a/capsule/report.json` |
| Fixed-slot-rotation Baseline A, previous record | `8ad3ad2fdc7bad34123c3987001f28062f44e39e55cd29a2801dc75ff1c5a987` | 57.54962903549228 Hz | 18.64848606376579 Hz | 13.591972683857533 ms | 10.581430141990426 ms | 0.7478364056237748 ms | 39,874,447.452961676 | `build/fixed-terrain-rotate-20260828/baseline-a/capsule/report.json` |
| Indexed-replay Baseline A, previous record | `e775171d8c9e07ddd2bd8387e703a778ab7a614789b0f58d3ec01ae408f0d501` | 59.294871794871796 Hz | 18.42948717948718 Hz | 13.34251048617445 ms | 10.35262836937737 ms | 0.7474050843694494 ms | 38,649,322.01689189 | `build/replay-indexed-loads-20260828/baseline-a/capsule/report.json` |
| Aligned-loop Baseline B, previous record | `e775171d8c9e07ddd2bd8387e703a778ab7a614789b0f58d3ec01ae408f0d501` | 59.441973311767086 Hz | 18.60088960776385 Hz | 12.75301347279859 ms | 9.89368199647547 ms | 0.7287624353362514 ms | 38,665,362.67687075 | `build/replay-aligned-accepted-loop-20260828/baseline-b/capsule/report.json` |
| Packed-replay Candidate B, previous record | `2945e4b4e0a6c9e22a32f3bc8650986b93a592ebe85b41adbb61fda413c167ef` | 59.80668546113572 Hz | 18.525976641159886 Hz | 12.121159669841099 ms | 9.325560789453078 ms | 0.696008338269382 ms | 38,169,628.78787879 | `build/packed-replay-records-20260828/candidate-b/capsule/report.json` |
| Task #187 Baseline A, retained-lineage record | `81900287fa9e19291a27667b0e23d5c0c6324e86e8b9d8da0ff82a65cc302823` | **60.15187849720224 Hz** | **18.585131894484412 Hz** | 9.426001134790807 ms | 7.291808423047645 ms | 0.5577711347390241 ms | **38,184,297.03654485** | `build/gui-deferred-demotions-20260829/baseline-a/capsule/report.json` |

The first row was 5.026178010471206 Hz short of 60. Task #125's retained-lineage observation then closed the measured gap to 0.19331453886427852 Hz. Tasks #127, #140, #145, #149, #153, #167, #185, #222, and #224 each retained a depressed/variable-host relative win without replacing the healthy absolute evidence. Task #187's unchanged-production Baseline A established the first controlled fixed-discriminator result above target, exceeding 60 Hz by 0.15187849720224267 Hz; sustained acceptance beyond the five-second discriminator remains separate.

## Sustained retained-lineage acceptance

The healthy Task #185 profiles and the current Task #224 screen use private inactive desktops, physical core 3 / affinity `0xc0`, and above-normal priority. Surface runs hold W for the first five seconds. Every run preserves the 320x200 full-fidelity renderer and measures presentation, authoritative simulation, renderer phases, deadlines, cycles, and input latency independently.

| Run | Presentation | Simulation | Missed deadlines | Maximum lateness | Render | Terrain | Input-to-present | Cycles/presentation | Classification | Evidence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| Moving surface, 30 seconds | 59.88741964493888 Hz | 18.252672950737768 Hz | 61 / 1,798 (3.3927%) | 22.004778839742166 ms | 11.166203353557002 ms | 10.311276996173417 ms | 25.557012669482106 ms | 38,085,058.08787542 | Healthy controlled; about three whole periods short of the ideal grid, so not final hitch-free acceptance | `build/sustained-native-acceptance-20260829/smoke-30s/surface/report.json` |
| Moving surface, 60 seconds | 59.800276745077774 Hz | 18.255172298818 Hz | 205 / 3,587 (5.7151%) | 22.385111828196283 ms | 11.564896158125006 ms | 10.556269442132269 ms | 20.31523311449872 ms | 38,427,630.569835514 | Healthy controlled; about 12 whole periods short of the ideal grid, so sustained smooth-pacing acceptance remains open | `build/sustained-native-acceptance-20260829/controlled-60s/surface/report.json` |
| Moving surface, 120 seconds | 49.93577660266569 Hz | 18.17438737551504 Hz | 3,190 / 5,987 (53.2821%) | 32.934633281630845 ms | 17.33770974936426 ms | 15.527246177930904 ms | 83.06802570352316 ms | 45,589,125.932019375 | Depressed before measurement: 8.476889099925756-second startup and 55.414247728783515-ms first input effect; not a healthy sustained-product conclusion | `build/sustained-native-acceptance-20260829/controlled-120s/surface/report.json` |
| Immediate capsule health control, 5 seconds | 59.97993981945837 Hz | 18.455366098294885 Hz | 0 / 299 (0%) | 0 ms | 9.38474271919088 ms | 7.2696296642784946 ms | n/a | 38,311,902.97993311 | Healthy controlled; separates the preceding depressed-host aggregate from production state | `build/sustained-native-acceptance-20260829/host-health-after-120s/capsule/report.json` |
| Task #222 previous production, 30 seconds | 50.60040026684457 Hz | 18.245496997998664 Hz | 999 / 1,517 (65.8537%) | 40.90546545212175 ms | 12.228818337739932 ms | 6.037122491054137 ms present | n/a | 45,270,688.3902439 | Controlled whole-period screen; authentic simulation passed, but host/presentation stalls prevented sustained acceptance | `build/restoring-fsqrt-20260830/sustained-30s/capsule/report.json` |
| Task #224 current production, 30 seconds | 49.79336088521531 Hz | 18.29756032528996 Hz | 1,012 / 1,494 (67.7376%) | 39.79539385847797 ms | 12.546715045912771 ms | 6.081586172609143 ms present | n/a | 45,989,303.979250334 | Controlled whole-period screen; authentic simulation passed, but host/presentation stalls prevented sustained acceptance | `build/buffered-limb-restoring-fsqrt-20260830/sustained-30s/capsule/report.json` |
| Orbital current production, 60 seconds | 48.38468068108054 Hz | 18.258684109785122 Hz | 1,118 / 2,907 (38.4589%) | 30.16377198842129 ms | 9.335608226735165 ms | 7.291947883076477 ms space | 6.303050545535515 ms | 47,357,984.064327486 | Healthy startup followed by severe late-run collapse; this exposed the spin-only fast wait | `build/sustained-native-acceptance-20260829/controlled-60s/orbital/report.json` |
| Rejected five-ms sleep margin, orbital 60 seconds | 56.68016194331984 Hz | 18.176971393345664 Hz | 1,199 / 3,402 (35.2440%) | 32.33348110384573 ms | 6.1325745499954625 ms | 4.84138871574068 ms space | 56.09996675163471 ms | 24,870,767.082010582 | Experimental only; coarse sleep overshoot prevented sustained acceptance despite short ABBA and fidelity wins | `build/fast-presenter-sleep-margin-20260829/candidate-sustained-60s/orbital/report.json` |
| Rejected zero-timeout yield, orbital 60 seconds | 59.768851585398345 Hz | 18.202104982680524 Hz | 1,115 / 3,589 (31.0671%) | 18.435593032286697 ms | 5.254932157837583 ms | 4.055254357371231 ms space | 8.145123710196383 ms | 38,411,549.71747005 | Experimental only; strongest sustained orbital result, rejected because Ordering B presentation reversed by 0.04755192797978358 Hz | `build/fast-presenter-sleep-margin-20260829/exploratory-yield-zero-60s/orbital/report.json` |
| Rejected alternate-frame zero yield, orbital 60 seconds | 52.56756306441401 Hz | 18.211203305674964 Hz | 1,300 / 3,155 (41.2044%) | 33.927779010428225 ms | 8.55144380092668 ms | 6.659641297548417 ms space | 61.64654981140448 ms | 43,613,019.52012678 | Experimental only; 30-Hz scheduler yielding did not prevent orbital collapse | `build/fast-presenter-alternate-yield-20260829/sustained-screen-60s-v2/orbital/report.json` |
| Rejected three-of-four zero yield, orbital 60 seconds | 59.27482571133127 Hz | 18.212748924246974 Hz | 1,142 / 3,554 (32.1328%) | 20.8169404973357 ms | 5.8931581544223555 ms | 4.558168016224683 ms space | 6.890430728241563 ms | 38,712,039.9780529 | Experimental only; 45-Hz scheduler yielding remained below the 59.7-Hz sustained screen | `build/fast-presenter-three-of-four-yield-20260829/sustained-screen-60s/orbital/report.json` |
| Rejected hoisted-timeout zero yield, orbital 60 seconds | 58.1693470515766 Hz | 18.163353644324577 Hz | 1,233 / 3,494 (35.2891%) | 24.950592666445107 ms | 6.421898173697441 ms | 4.977952582499275 ms space | 82.77943945939958 ms | 39,424,451.52146537 | Experimental only; every-presentation yield had zero timed sleeps, but sustained presentation and simulation both failed admission | `build/fast-presenter-hoisted-timeout-yield-20260829/sustained-screen-60s/orbital/report.json` |
| Task #204 unchanged production, orbital 60 seconds | 28.43846949327818 Hz | 18.264002401841413 Hz | 1,158 / 1,705 (67.9179%) | 50.89347270098966 ms | 25.28808434582388 ms | 19.904436588509867 ms space | 9.089736461692427 ms | 80,582,071.83049853 | Depressed-host evidence only; pre-run production control was 59.988 Hz but the immediate post-run capsule remained depressed at 56.080 Hz | `build/sustained-production-recheck-20260829/orbital/report.json` |

The healthy 30- and 60-second runs preserve authentic simulation and stay close to the nominal 60-Hz grid, but both contain whole-period stalls and the terminal aggregate has no per-presentation pose trace. They therefore do **not** yet satisfy the stronger requirement for no duplicated-pose hitch or catch-up burst. The depressed 120-second run is retained honestly but is not averaged with healthy evidence.

## Historical production observations

These are useful host-state observations, not replacements for the healthy record.

| Checkpoint | Presentation | Simulation | Cycles/presentation | Classification | Evidence |
|---|---:|---:|---:|---|---|
| Task #50 production recheck | 39.603960396 Hz | 18.976897690 Hz | Not retained in task summary | Historical task-record summary; host class not preserved | Completed Task #50 record |
| Task #85 accepted square-table production recheck | 35.64880831126502 Hz | 18.944795273986557 Hz | 62,802,012.05142857 | Depressed-host absolute observation | `build/production-square-recheck-20260828/capsule/report.json` |
| Task #141 folded-destination production recheck | 50.82000404940271 Hz | 18.829722615914154 Hz | 45,043,949.79681275 | Depressed-host absolute observation; healthy record unchanged | `build/folded-pair-destination-production-recheck-20260828/capsule/report.json` |

## Earlier experimental healthy-host peak rejected after full ABBA

At the time, the exact 1-KiB hybrid terrain-root candidate produced a higher isolated Candidate A result than the then-retained record. Acceptance still required both orderings. Host conditions changed sharply before Ordering B; the evidence classes remain separate rather than being averaged.

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | **57.71976341015705 Hz** | 18.764022027330206 Hz | 13.829992888884002 ms | 10.678777814731673 ms | 0.7497625374158181 ms | 39,747,340.56890459 |
| Baseline A | 54.855749695245834 Hz | 18.69158878504673 Hz | 15.070758259650859 ms | 11.717779426616376 ms | 0.8233788824996393 ms | 41,838,132.825925924 |
| Baseline B | 37.76717161236771 Hz | 18.883585806183856 Hz | 24.972034587560465 ms | 19.64219180930366 ms | 1.4668690797238377 ms | 60,478,207.428571425 |
| Candidate B | 36.087758868156655 Hz | 18.864055771990976 Hz | 26.12363952020202 ms | 20.618669823232324 ms | 1.499153409090909 ms | 63,271,407.39772727 |

- Ordering A: candidate gained 2.8640137149112164 Hz and removed 2,090,792.2570213303 cycles/presentation.
- Ordering B: candidate lost 1.6794127442110565 Hz and added 2,793,199.969155848 cycles/presentation.
- Disposition: rejected after Ordering B; fidelity skipped; accepted production restored.
- Evidence: `build/hybrid-depth-root-20260828/result.json`.

## Retained ABBA checkpoints

### Terrain square lookup — Task #81

| Run | Presentation | Simulation | Terrain | Cycles/presentation |
|---|---:|---:|---:|---:|
| Candidate A | 36.86449260684626 Hz | 18.83735061778408 Hz | 20.180204517704517 ms | 61,793,284.983516484 |
| Baseline A | 35.816618911174785 Hz | 18.82930822758903 Hz | 20.317069483046136 ms | 63,828,237.01142857 |
| Baseline B | 37.12720632988436 Hz | 18.867924528301888 Hz | 19.963073448551512 ms | 60,797,699.03825136 |
| Candidate B | 41.33577682753003 Hz | 18.733455508043168 Hz | 18.048480542254808 ms | 55,401,491.37438424 |

- Ordering A: +1.047873695671477 Hz and -2,034,952.0279120877 cycles/presentation.
- Ordering B: +4.208570497645674 Hz and -5,396,207.663867123 cycles/presentation.
- Synchronized authoritative renderer/gameplay fidelity passed; baseline-controlled live-UTC telemetry differences were excluded as capture nondeterminism.
- Retained executable: `8ad3ad2fdc7bad34123c3987001f28062f44e39e55cd29a2801dc75ff1c5a987`.
- Evidence: `build/depth-square-lookup-20260828/result.json`.

### Layout-stable i386m multiply-by-200 — Task #98

| Run | Presentation | Simulation | Terrain | Cycles/presentation |
|---|---:|---:|---:|---:|
| Candidate A | 45.38021259198692 Hz | 18.806214227309894 Hz | 16.330135570715765 ms | 50,422,532.68918919 |
| Baseline A | 37.89731051344743 Hz | 18.744906275468622 Hz | 19.512840037936613 ms | 60,317,375.91935484 |
| Baseline B | 47.051696284329566 Hz | 18.780290791599352 Hz | 15.790322980690988 ms | 48,706,945.53218884 |
| Candidate B | 47.60940032414911 Hz | 18.638573743922205 Hz | 15.402947300673885 ms | 48,091,463.70638298 |

- Ordering A: +7.482902078539489 Hz and -9,894,843.230165653 cycles/presentation.
- Ordering B: +0.5577040398195408 Hz and -615,481.8258058578 cycles/presentation.
- Compiler self-hosting fixpoint, 17 exact same-size substitutions, edge semantics, synchronized indexed-page/state fidelity, and toolchain gates passed.
- Retained executable after this checkpoint: `a06008e652cc253e8a532f7f6cdb29cee20a43ac6f27cfe6dc71a2ee9a9160af`.
- Evidence: `build/i386m-fixed-mul200-codegen-20260828/result.json`.

### Layout-stable terrain replay cursor/count retention — Task #106

| Run | Presentation | Simulation | Terrain | Cycles/presentation |
|---|---:|---:|---:|---:|
| Candidate A | 36.886907174706124 Hz | 19.051479529793273 Hz | 20.143804808931186 ms | 62,064,193.807692304 |
| Baseline A | 36.23040911866477 Hz | 18.92937105638103 Hz | 20.5902728983334 ms | 62,791,225.19662921 |
| Baseline B | 35.909920876445526 Hz | 19.07080543720836 Hz | 20.777090332565777 ms | 63,604,588.56497175 |
| Candidate B | 37.105371053710535 Hz | 18.86018860188602 Hz | 20.003200418596776 ms | 61,969,457.160220996 |

- Ordering A: +0.656498056041354 Hz and -727,031.388936907 cycles/presentation.
- Ordering B: +1.195450177265009 Hz and -1,635,131.404750754 cycles/presentation.
- Synchronized indexed-page and semantic-state fidelity: exact.
- Retained executable after this checkpoint: `e775171d8c9e07ddd2bd8387e703a778ab7a614789b0f58d3ec01ae408f0d501`.
- Evidence: `build/replay-register-retention-padded-20260828/result.json`.
- Published implementation: commit `409abb2` (`Retain terrain replay cursors in registers`).

### Packed terrain replay records — Task #125

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | 53.2483552631579 Hz | 18.70888157894737 Hz | 17.57947668613595 ms | 13.864096092286992 ms | 0.9981466324418601 ms | 42,602,587.91505791 |
| Baseline A | 47.19645018152481 Hz | 18.55586930213796 Hz | 18.09484515656876 ms | 14.111232926838516 ms | 1.0161043235577398 ms | 48,430,152.77350427 |
| Baseline B | 51.03256552819698 Hz | 18.46703733121525 Hz | 14.700143158848402 ms | 11.27143081909165 ms | 0.8085332528785215 ms | 44,551,351.44357976 |
| Candidate B | **59.80668546113572 Hz** | **18.525976641159886 Hz** | 12.121159669841099 ms | 9.325560789453078 ms | 0.696008338269382 ms | **38,169,628.78787879** |

- Ordering A: +6.0519050816330875 Hz and -5,827,564.85844636 cycles/presentation.
- Ordering B: +8.774119932938738 Hz and -6,381,722.655700974 cycles/presentation.
- Candidate A passed the 18.206-Hz simulation gate; both orderings won both mandatory metrics independently.
- Each ordered terrain byte store is retained as one packed shared-Lino command with a 16-bit page offset and exact byte value; the exact 118-word terminal raster state remains unchanged.
- The candidate and accepted executable are both 646,594 bytes. Exact local dead padding restores every downstream offset around nine intentional change regions.
- An independent baseline repeat confines nondeterminism to host-timing, live-UTC, and its rendered telemetry island. Candidate and baseline are exact across every authoritative renderer product and gameplay state after those baseline-controlled exclusions.
- Retained executable: `2945e4b4e0a6c9e22a32f3bc8650986b93a592ebe85b41adbb61fda413c167ef`.
- Candidate B is the new retained healthy-host absolute record, 0.19331453886427852 Hz short of the external 60-Hz target.
- Evidence: `build/packed-replay-records-20260828/result.json`.

### Culling-pair terrain replay — Task #127

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | 52.7829123023208 Hz | 18.895050318340523 Hz | 17.597309320157198 ms | 13.817707844971556 ms | 0.9919776518449542 ms | 43,495,526.92607004 |
| Baseline A | 40.12841091492777 Hz | 18.258426966292134 Hz | 23.527697434188603 ms | 18.59883261135177 ms | 1.3101038542707986 ms | 56,971,436.595 |
| Baseline B | 48.75601926163724 Hz | 18.65971107544141 Hz | 16.592855451417748 ms | 12.774296612641178 ms | 0.9142988800842611 ms | 46,903,230.481481485 |
| Candidate B | 57.23498589278517 Hz | 18.540910923014913 Hz | 14.710946576710624 ms | 11.46324316823797 ms | 0.8150301116506452 ms | 40,058,763.74647887 |

- Ordering A: +12.654501387393033 Hz and -13,475,909.668929957 cycles/presentation.
- Ordering B: +8.478966631147927 Hz and -6,844,466.735002615 cycles/presentation.
- Candidate A passed the 18.206-Hz simulation gate; both orderings independently won presentation throughput and cycles/presentation.
- The shared-Lino culling path retains the first two independent scratch-command decodes, then decodes each proved adjacent equal-value command pair once and performs both exact ordered stores. Ordinary records retain Task #125's accepted one-command loop, `PGtrcount` remains the ordered-store count, and the exact 118-word terminal state remains unchanged.
- The fixed replay entry ends at the accepted `0x2fa89` downstream offset. Every pre-existing code byte from there through the former final return at `0x9b34e` is exact; the 133-byte shared-Lino culling routine replaces one final padding byte, and the old packaging suffix is byte-exact after the resulting 132-byte shift.
- Independent baseline-repeat control confines nondeterminism to host timing, live UTC, and its rendered telemetry island. Candidate and baseline are exact across every authoritative renderer and gameplay product after those exclusions.
- Retained executable: `90fe4e4782baa08b2ae69eec012278a4e70d767314d5769ae45b2e83126b1b21` (646,726 bytes).
- This variable/depressed-host ABBA pass does not replace Task #125's 59.80668546113572-Hz healthy absolute record.
- Evidence: `build/culling-pair-replay-20260828/result.json`.

### Folded paired culling-replay destination — Task #140

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | 39.43154523618895 Hz | 18.815052041633308 Hz | 23.940022560631697 ms | 18.879062041737168 ms | 1.3471257755217145 ms | 57,791,753.964467004 |
| Baseline A | 36.985759493670884 Hz | 18.789556962025316 Hz | 25.543413147837505 ms | 20.166114940259536 ms | 1.4391662915482097 ms | 61,608,602.57754011 |
| Baseline B | 36.43061809250921 Hz | 19.03397462136717 Hz | 25.960073681671684 ms | 20.406215828812584 ms | 1.4439639389701813 ms | 62,443,203.494382024 |
| Candidate B | 37.63658437879401 Hz | 18.818292189397006 Hz | 25.002916175949593 ms | 19.750691791380614 ms | 1.5326973161366921 ms | 60,202,184.758064516 |

- Ordering A: +2.445785742518069 Hz and -3,816,848.613073103 cycles/presentation.
- Ordering B: +1.2059662862848057 Hz and -2,241,018.736317508 cycles/presentation.
- Candidate A passed the 18.206-Hz simulation gate; both orderings independently won presentation throughput and cycles/presentation.
- The shared-Lino culling-pair loop now writes the second exact destination as `D plus 1` directly, removing the hot `D+` while preserving the same ordered stores. The next iteration reloads D, and the terminal state load overwrites it on exit.
- One unreachable `A+` supplies cold same-size padding. The 28-byte generated replacement range moves the second store displacement by one Lino word, keeps the loop and finish targets exact, and leaves the prefix, suffix, and 646,726-byte file size exact.
- Independent baseline-repeat control and the candidate are exact across every authoritative renderer and gameplay product after the established host-timing and live-UTC telemetry exclusions.
- Retained executable: `6038ddf024f84e75efc02e537edbf788411aa3efdacc1fb76c426362674c17fd` (646,726 bytes).
- This depressed-host ABBA pass does not replace Task #125's 59.80668546113572-Hz healthy absolute record.
- Evidence: `build/folded-pair-destination-20260828/result.json`.

### Direct culling-pair command load — Task #145

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | 42.329134833780714 Hz | 18.790006194507537 Hz | 22.10189973171003 ms | 17.40782137150701 ms | 1.2970596612873035 ms | 53,854,935.741463415 |
| Baseline A | 36.77830285596877 Hz | 18.69734949660982 Hz | 25.487737535621815 ms | 20.093669397310546 ms | 1.5512699789215632 ms | 62,088,699.2122905 |
| Baseline B | 37.07414829659319 Hz | 18.637274549098198 Hz | 25.4409257823534 ms | 20.061403698561804 ms | 1.4727409864834815 ms | 61,248,854.88108108 |
| Candidate B | 46.000407083248525 Hz | 18.522287807856706 Hz | 19.940090663094022 ms | 15.833494344345178 ms | 1.3276778419751296 ms | 49,124,978.88495575 |

- Ordering A: +5.550831977811946 Hz and -8,233,763.470827088 cycles/presentation.
- Ordering B: +8.926258786655339 Hz and -12,123,875.996125333 cycles/presentation.
- Candidate A passed the 18.206-Hz simulation gate; both orderings independently won presentation throughput and cycles/presentation.
- The shared-Lino culling-pair loop replaces `A = PGtrcommands; A + B; D = [A]` with one `D = [B relating PGtrcommands]` load. The generated displacement proves `(PGtrcommands + B) * 4 = PGtrcommands * 4 + B * 4`; command decode, ordered stores, cursor/count updates, terminal state, and observable raster scratch are unchanged.
- Seven added unreachable A-padding bytes preserve the accepted footprint after the hot address sequence shrinks from 14 to seven bytes. The loop target remains `0x9b398`, the finish target remains `0x2fa79`, and the prefix, suffix, and 646,726-byte file size are exact.
- Independent baseline-repeat control and the candidate are exact across every authoritative renderer and gameplay product after the established host-timing and live-UTC telemetry exclusions.
- Retained executable: `10bb7ddb58d1c124c0acc666aada1f7804d093e59142b162ded162b0555d7aca` (646,726 bytes).
- This depressed-host ABBA pass does not replace Task #125's 59.80668546113572-Hz healthy absolute record.
- Evidence: `build/direct-pair-command-load-20260828/result.json`.

### Generalized exact i386m register low16 code generation — Task #149

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | 37.743589743589745 Hz | 18.871794871794872 Hz | 24.921544329310336 ms | 19.67807969005405 ms | 1.4430116302057465 ms | 59,996,166.407608695 |
| Baseline A | 34.99190938511327 Hz | 19.01294498381877 Hz | 26.901813322169804 ms | 21.2300925821566 ms | 1.6097199993559503 ms | 63,200,629.73988439 |
| Baseline B | 38.35562549173879 Hz | 18.68607395751377 Hz | 24.54603114956174 ms | 19.386095145371264 ms | 1.4188873041765238 ms | 58,999,069.22051282 |
| Candidate B | 39.88941548183254 Hz | 18.562401263823066 Hz | 23.59687807211572 ms | 18.619220582297594 ms | 1.3380671345060038 ms | 56,892,047.06435644 |

- Ordering A: +2.7516803584764773 Hz and -3,204,463.332275696 cycles/presentation.
- Ordering B: +1.5337899900937515 Hz and -2,107,022.1561563835 cycles/presentation.
- Candidate A passed the 18.206-Hz simulation gate; both orderings independently won presentation throughput and cycles/presentation.
- The compiler's guarded i386m target-code generation replaces 204 five-byte `AND EAX,0x0000FFFF` instructions and 118 six-byte EBX/ECX/EDX forms with exact three-byte same-register `MOVZX` instructions. Stage 2 and stage 3 are byte-identical; focused A-through-E outputs match exactly; whole-generated-code flag liveness proves all six AND-written status flags dead at all 322 sites.
- Full instruction normalization accounts for every replacement, branch/call target, five embedded code offsets, three application-header fields, twelve workspace offsets, entry/tail alignment, and the exact shifted package suffix. The generated instructions save 762 bytes and the aligned executable saves 760 bytes.
- Independent baseline-repeat control and the candidate are exact across every authoritative renderer and gameplay product after the established host-timing and live-UTC telemetry exclusions.
- Retained compiler: `e29b89695442d6b608041becc0d593b224ba68e707993ddd6c85c44f9f264dbe` (81,332 bytes).
- Retained executable: `1a9b312e3173f06428aa305e003e0ebe9769b42c8a8c05253c057f0f9e462e89` (645,966 bytes).
- The shared Lino gameplay/renderer source is unchanged. This depressed-host ABBA pass does not replace Task #125's 59.80668546113572-Hz healthy absolute record.
- Evidence: `build/i386m-general-low16-codegen-20260828/result.json`.

### Reversed terrain replay fields — Task #153

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | 37.925379253792535 Hz | 18.24518245182452 Hz | 24.907782423251852 ms | 19.553256698061244 ms | 1.434912694184328 ms | 60,394,619.89189189 |
| Baseline A | 37.411526794742166 Hz | 18.806875631951467 Hz | 24.72940865225626 ms | 19.51040675825993 ms | 1.7071226287466557 ms | 60,875,744.902702704 |
| Baseline B | 38.0057212913772 Hz | 19.0028606456886 Hz | 24.763598461240896 ms | 19.542884194288636 ms | 1.4373189677610387 ms | 60,058,473.182795696 |
| Candidate B | 38.46153846153846 Hz | 18.93491124260355 Hz | 24.055055657701573 ms | 19.01309160359744 ms | 1.6462997961830648 ms | 58,273,958.84615385 |

- Ordering A: +0.5138524590503692 Hz and -481,125.0108108148 cycles/presentation.
- Ordering B: +0.4558171701612608 Hz and -1,784,514.336641848 cycles/presentation.
- Candidate A passed the 18.206-Hz simulation gate; both orderings independently won presentation throughput and cycles/presentation.
- The three ordinary, three culling-pair, and two scratch producers retain exact values while packing destinations into the high half of each shared-Lino replay command. All three decoders recover the exact low 16-bit value and high 16-bit destination before the same 32-bit ordered stores.
- The guarded i386m compiler delays only exact adjacent `C = D`, folds an immediately following exact `C & 65535` to `MOVZX ECX,DX`, and emits the ordinary `MOV ECX,EDX` at every mismatch or code boundary. Stage 2 and stage 3 are byte-identical. Exact private-desktop fixtures cover fold, mismatch, label, raw-code, and source-end behavior.
- Production disassembly proves exactly three folds at `0x2f95d`, `0x9b06e`, and `0x9b0a8`; all 415 changed bytes lie in eleven explicit producer/decoder ranges, with zero unexpected changes. The 645,966-byte executable, common finish `0x2f97a`, culling entries `0x9b060` and `0x9b0a1`, and downstream appendix `0x9b0d2` remain exact.
- Independent baseline-repeat control and the candidate are exact across every authoritative renderer and gameplay product after the established host-timing and live-UTC telemetry exclusions.
- Retained compiler: `04e98c971c4f61002529ed5a3b0a1c1587288a9b7ad30fcad19228286edb77de` (81,956 bytes).
- Retained executable: `fd0f7912d2ebe84b3fdea8a759f1226465d5516a6965ed01faec94e1aa5985d2` (645,966 bytes).
- This depressed-host ABBA pass does not replace Task #125's 59.80668546113572-Hz healthy absolute record.
- Evidence: `build/reversed-terrain-replay-fields-20260828/result.json`.

### Exact scalar delta-pointer layer copy — Task #167

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | 38.19375372985876 Hz | 18.897951064253032 Hz | 24.345452657421845 ms | 19.440835700230192 ms | 1.655531229115616 ms | 59,792,707.1875 |
| Baseline A | 36.59292950175729 Hz | 18.81331403762663 Hz | 25.699405058600696 ms | 20.20389517645414 ms | 1.5193388871228952 ms | 62,520,265.05649717 |
| Baseline B | 38.5885266198927 Hz | 18.984729673957904 Hz | 24.27083257781358 ms | 19.164344421886195 ms | 1.5932874175492624 ms | 59,564,663.93582888 |
| Candidate B | 41.14636642784033 Hz | 18.62845445240532 Hz | 22.54615004594508 ms | 17.710776706924623 ms | 1.561922401779604 ms | 55,827,592.258706465 |

- Ordering A: +1.600824228101473 Hz and -2,727,557.8689971715 cycles/presentation.
- Ordering B: +2.55783980794763 Hz and -3,737,071.677122414 cycles/presentation.
- Candidate A passed the 18.206-Hz simulation gate by 0.6919510642530327 Hz; both orderings independently won presentation throughput and cycles/presentation.
- One zero-byte label after the shared-Lino layer-copy register saves selects the exact i386m-only compiler lowering. All other targets retain the original pure-Lino scalar loop; no target-specific Lino fork, raw target-machine block, native gameplay/renderer code, or CPU-pack change was introduced.
- The guarded backend recognizes only the exact 23-byte scalar copy body plus the existing `POP ECX; POP EBX; POP EAX`, retains `A-B` in EAX, advances one destination byte pointer in EBX, and preserves every source address, destination/value store, overlap result, and final EBP value. Its changed CF is overwritten by the existing post-pop ADD before any observation.
- The 20-case overlap/store-order model, 10,000-case modular address proof, one positive and six fail-closed negative compiler fixtures, 26-check toolchain regression, zero-warning three-stage byte-identical compiler fixpoint, and exact production disassembly/layout proof passed. Exactly 17 byte values changed inside `[0x1a6bc,0x1a6d3)`; the existing pops and every prefix, suffix, downstream address, and 645,966-byte file layout remain exact.
- The full-frame model preserves 256,000 loads, 256,000 ordered stores, 256,000 loop branches, and 2,048,000 bytes of copy traffic while removing an estimated 254,800 dynamically executed instructions.
- Independent baseline-repeat control and the candidate are exact across every authoritative renderer/gameplay product after only the established host-timing and live-UTC telemetry exclusions.
- Retained compiler: `fd9de5f91799156d95c34d67a6d40fae4347bd7c7409aee9fcfe324a72a5850a` (82,600 bytes).
- Retained executable: `602385f436cae6ab5b49d89f044b1fccf5d565b8679c13b023ea1bdf1d993a65` (645,966 bytes); CPU pack remains `1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7`.
- This same-host depressed/variable-host ABBA retention does not replace Task #125's 59.80668546113572-Hz healthy absolute record; the measured target gap remains 0.19331453886427852 Hz.
- Evidence: `build/scalar-delta-layer-copy-20260829/result.json`.

### Physical-base/block-index GUI lowering — Task #180

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | 50.40280933691386 Hz | 18.79776905598017 Hz | 18.132617847802514 ms | 14.284454478353183 ms | 1.038682692570554 ms | 45,381,634.03278688 |
| Baseline A | 40.168708576019284 Hz | 18.879293030729063 Hz | 23.5087267771721 ms | 18.582861831126934 ms | 1.3398970964512182 ms | 56,953,089.805 |
| Baseline B | 37.93445878848063 Hz | 18.867924528301888 Hz | 24.657584068893783 ms | 19.433576421776852 ms | 1.5911058684068313 ms | 59,873,642.70157068 |
| Candidate B | 49.05353144718095 Hz | 18.725829432118868 Hz | 18.796846380615293 ms | 14.75097727545768 ms | 1.0700699572124315 ms | 46,619,244.946058095 |

- Ordering A: +10.234100760894577 Hz and -11,571,455.772213116 cycles/presentation.
- Ordering B: +11.119072658700318 Hz and -13,254,397.755512588 cycles/presentation.
- Candidate A and Candidate B passed the authentic simulation gate by 0.5917690559801692 Hz and 0.5198294321188683 Hz respectively; both orderings independently won both mandatory metrics and contradictory orderings were not averaged.
- Two zero-byte labels after the unchanged shared-Lino compose and fixed-2x loops select exact full-signature i386m backend replacements. All shipping targets retain the same tracked `work/vhgame.txt` / `work/vhgui.txt` dependency closure; no architecture-specific gameplay/renderer source fork, raw target-machine block, native replacement, or CPU-pack change was introduced.
- The two same-size replacements save B in compiler-private EBP, convert C/D/E to physical workspace bases, and use B as a four-pixel block index. They restore exact logical terminal registers before the unchanged outer counter tails and add no native stack memory operations.
- The 256-case ordered-event/address/state model, explicit modular-wrap cases, twelve byte-identical fail-closed negative fixtures, 28-check toolchain regression, byte-identical three-stage compiler fixpoint, and production disassembly/layout proof passed. Exactly 340 byte values changed inside `[0x771ef,0x77297)` and `[0x77401,0x774d3)`; no external branch enters either island or its unreachable post-RET padding, and every downstream byte and address remains exact.
- The exact full-presentation traces retain 192,000 compose and 320,000 fixed-2x ordered workspace events while removing 42,800 dynamically executed instructions and 2,239,600 dynamically fetched encoded bytes per presentation.
- Synchronized baseline, independent baseline-repeat, and candidate captures used `clock=1344638527 quit freeze` on private inactive desktops. The checkpoint and all authoritative renderer/gameplay/state products matched exactly after only the established host-timing and live-UTC telemetry exclusions.
- Retained compiler: `07e4a47828d985b6345b9a88ad0d1403b8bc8c9b79d48fd39d118073ce4dd5c2` (86,288 bytes).
- Retained executable: `109b9dea631a09f1b1280f8e315a020cf10ebc3ffda5a63d3062123b8dfdbfc0` (645,966 bytes); CPU pack remains `1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7`.
- This controlled depressed/variable-host ABBA retention does not replace Task #125's 59.80668546113572-Hz healthy absolute record; the measured target gap remains 0.19331453886427852 Hz.
- Evidence: `build/gui-block-index-20260829/result.json`; source, semantic, fixture, fixpoint, layout, fidelity, manifest, and storage proofs are retained in the same directory.

### Counter-preserving memory-CMP GUI backedges — Task #185

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | 58.98876404494382 Hz | 18.459069020866774 Hz | 12.344813868734356 ms | 9.451278114441516 ms | 0.6822547261248041 ms | 38,862,579.76530612 |
| Baseline A | 57.07901685963843 Hz | 18.484663822872232 Hz | 14.691647966981302 ms | 11.379617547681722 ms | 0.8268887937008973 ms | 40,207,629.59786477 |
| Baseline B | 57.86438655796381 Hz | 18.492742095844104 Hz | 14.05703499024427 ms | 10.960868050234192 ms | 0.8253190722030717 ms | 39,464,986.512027495 |
| Candidate B | 59.50446791226645 Hz | 18.480909829406986 Hz | 12.583441907139646 ms | 9.702758267336376 ms | 0.7042225925984876 ms | 38,630,169.45051195 |

- Ordering A: +1.9097471853053918 Hz and -1,345,049.8325586468 cycles/presentation.
- Ordering B: +1.6400813543026374 Hz and -834,817.0615155473 cycles/presentation.
- Candidate A and Candidate B passed the authentic simulation gate by 0.25306902086677496 Hz and 0.2749098294069867 Hz respectively; both orderings independently won both mandatory metrics and contradictory orderings were not averaged.
- The two existing zero-byte shared-Lino markers and every shared `work/vhgui.txt` / `work/vhgame.txt` byte and operation remain unchanged. The compiler-owned refinements retain each `VHGUIx` decrement/write and its exact ordered dword read, replacing only `MOV EAX,[VHGUIx]; CMP EAX,0` with equivalent `CMP dword [VHGUIx],0`. No architecture-specific Lino fork, raw target-machine block, native gameplay/renderer replacement, or CPU-pack change was introduced.
- One-row counter/read/write/branch modeling proves the exact `79…0` write trace, 79-taken/one-fallthrough branch trace, comparison flags for every dword value, and dead EAX value on both successors. The twelve byte-identical fail-closed negative fixtures, 28-check toolchain regression, zero-warning three-stage byte-identical compiler fixpoint, and full production disassembly/layout proof passed.
- Exactly 127 byte values changed inside `[0x771ef,0x77297)` and `[0x77401,0x774d3)`; no external branch enters either island or its unreachable post-RET padding, and every byte and address outside the islands remains exact. The model removes 32,000 dynamically executed instructions and 64,000 dynamically fetched encoded bytes per presentation while preserving all 32,000 counter dword reads, all counter writes, pixel traffic, branches, terminal registers/flags, and native stack traffic.
- Synchronized baseline, independent baseline-repeat, and candidate captures used `clock=1344638527 quit freeze` on private inactive desktops. The checkpoint and all authoritative renderer/gameplay/state products matched exactly after only the established host-timing and live-UTC telemetry exclusions.
- Retained compiler: `cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87` (86,288 bytes).
- Retained executable: `81900287fa9e19291a27667b0e23d5c0c6324e86e8b9d8da0ff82a65cc302823` (645,966 bytes); CPU pack remains `1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7`.
- Candidate B reached 59.50446791226645 Hz on this controlled near-record/variable-host run. It does not replace Task #125's 59.80668546113572-Hz healthy absolute record; the measured target gap remains 0.19331453886427852 Hz.
- Task #186 then ran one unchanged-production fixed discriminator and reached 59.43985492645577 Hz at 18.537175095708243-Hz simulation, 12.39011636139815-ms render, 9.577465953481873-ms terrain, 0.7022367896866379-ms present, and 38,646,174.55932204 cycles/presentation. This controlled near-record observation is 0.36683053467994853 Hz below the existing healthy record, so no second unchanged recheck was run.
- Evidence: `build/gui-memory-cmp-backedge-20260829/result.json`; source, semantic, fixture, fixpoint, layout, fidelity, ABBA, healthy-recheck, manifest, and storage proofs are retained in the same directory.

### Buffered-limb restoring square root — Task #224

| Run | Presentation | Simulation | Render | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|
| Candidate A | 54.69703131354209 Hz | 18.70679137860919 Hz | 16.284853001367207 ms | 1.0292867886094248 ms | 41,926,568.888475835 |
| Baseline A | 53.498779495524815 Hz | 18.51098454027665 Hz | 16.791500618473957 ms | 1.0746562834160083 ms | 42,843,247.17490494 |
| Baseline B | 55.24193548387097 Hz | 18.75 Hz | 15.491653979395927 ms | 1.000229141437451 ms | 41,342,567.33941606 |
| Candidate B | 56.59995957145745 Hz | 18.597129573478878 Hz | 14.61919037563903 ms | 0.9015634426697996 ms | 40,547,182.532142855 |

- Ordering A: +1.198251818017276 Hz and -916,678.2864291072 cycles/presentation.
- Ordering B: +1.3580240875864789 Hz and -795,384.8072732016 cycles/presentation.
- Candidate A and Candidate B passed the authentic simulation gate by 0.5007913786091898 Hz and 0.391129573478878 Hz respectively; both orderings independently won both mandatory metrics and contradictory orderings were not averaged.
- The common tracked `work/fp/fpsoft.txt` helper retains all 64 restoring decisions but buffers one fixed 32-bit radicand limb in direct scratch. The hot loop performs 64 direct buffer reads/writes and zero dynamic pointer reads; three cold handoffs load and clear the next source limb. The model proves four pointer decrements, the guarded terminal `srd0-1` pointer without a dereference, zero terminal source limbs/value buffer, the accepted equality-borrow residual, and exact public p64/p53 results.
- The buffered handoff consumes Task #222's existing 20-byte unreachable calibration footprint. All 731 changed byte values remain confined to the exact 1,112-byte helper island `[0x256f1,0x25b49)`; the candidate `ret` is the final island byte at `0x25b48`, and every package byte/address after it is exact.
- Synchronized baseline, independent baseline-repeat, and candidate captures used `clock=1344638527 quit freeze` on private inactive desktops. All authoritative renderer/gameplay/state products matched exactly after only the established host-timing and live-UTC telemetry exclusions.
- Retained shared-Lino source: `work/fp/fpsoft.txt`, SHA-256 `063ecf40b0faab3b2779d8ff159b8fa815eec7b397de0d47e68223841e2a59cc`.
- Retained executable: `e18e8eb45ac0bc03aa2ee1f51ce1ae54f6ee00a0e8a7cef24cbd3adebcdf32a0` (645,966 bytes); compiler remains `cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87` and CPU pack remains `1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7`.
- This controlled variable/depressed-host retention does not replace the 60.15187849720224-Hz healthy absolute record. A separate current-production 30-second screen reached 49.79336088521531-Hz presentation and 18.29756032528996-Hz simulation with 1,012 / 1,494 missed deadlines, so sustained 60-Hz acceptance remains open.
- Evidence: `build/buffered-limb-restoring-fsqrt-20260830/result.json`; exact transform, model, semantic review, private build, layout, ABBA, synchronized fidelity, sustained screen, and manifest proofs are retained in the same directory.

### Exact restoring square root — Task #222

| Run | Presentation | Simulation | Render | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|
| Candidate A | 56.17072679685927 Hz | 18.522246829071875 Hz | 14.815544434008036 ms | 0.9172424616860297 ms | 40,747,194.59139785 |
| Baseline A | 51.6545601291364 Hz | 18.563357546408394 Hz | 17.598718628337043 ms | n/a | 44,246,091.64453125 |
| Baseline B | 56.08616134931924 Hz | 18.89859784596627 Hz | 14.567818902597162 ms | n/a | 40,935,510.33695652 |
| Candidate B | 57.85288270377733 Hz | 18.48906560636183 Hz | 13.909757823416042 ms | n/a | 39,428,712.95532646 |

- Ordering A: +4.516166667722868 Hz and -3,498,897.0531333983 cycles/presentation.
- Ordering B: +1.7667213544580909 Hz and -1,506,797.381630063 cycles/presentation.
- Candidate A and Candidate B passed the authentic simulation gate by 0.3162468290718752 Hz and 0.28306560636182976 Hz respectively; both orderings independently won both mandatory metrics and contradictory orderings were not averaged.
- The common tracked `work/fp/fpsoft.txt` helper replaces 64 trial-square decisions plus one residual square with one 64-iteration restoring integer root. It reproduces the accepted private equality-borrow residual before p64 rounding and preserves public p53 binary64 results and helper state; no architecture-specific Lino fork, raw target-machine block, native gameplay/renderer replacement, compiler change, or CPU-pack change was introduced.
- The model covered 65,548 normalized mantissas, 92,146 binary64 pipeline cases, 24 special dispatch cases, and 4,096 public-state cases. The generated helper makes zero `Mul128` calls instead of 65 per positive root.
- The candidate helper body is 20 bytes shorter, and four unreachable shared-Lino assignments preserve the exact 1,112-byte generated island. All 755 changed byte values are confined to `[0x256f1,0x25b49)`; every package byte and address outside that helper is exact.
- Synchronized baseline, independent baseline-repeat, and candidate captures used `clock=1344638527 quit freeze` on private inactive desktops. The checkpoint and all authoritative renderer/gameplay/state products matched exactly after only the established host-timing and live-UTC telemetry exclusions.
- Retained shared-Lino source: `work/fp/fpsoft.txt`, SHA-256 `6b2e209be5b62013276514f8c418cafc92ecb9fd4d9fd6fbdf91453bfebe66d3`.
- Retained executable: `c4a62f5068262239a8a5665c443a75784fa2472941c9dfdb8fb731f5c8217ca2` (645,966 bytes); compiler remains `cfb39efc611dc96eab47f24c70cc7447a11f3b7cd874c49bfeb4934a42e67e87` and CPU pack remains `1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7`.
- This controlled variable/depressed-host retention does not replace the 60.15187849720224-Hz healthy absolute record. A separate current-production 30-second screen reached 50.60040026684457-Hz presentation and 18.245496997998664-Hz simulation with 999 / 1,517 missed deadlines, so sustained 60-Hz acceptance remains open.
- Evidence: `build/restoring-fsqrt-20260830/result.json`; model, semantic review, build, exact layout, ABBA, synchronized fidelity, sustained screen, and manifest proofs are retained in the same directory.

## Rejected full-ABBA candidates

### Limb-pointer restoring square root — Task #223

| Run | Presentation | Simulation | Render | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|
| Candidate A | 58.137195735264534 Hz | 18.507342587004626 Hz | 13.806023541116485 ms | 0.8503744162560068 ms | 39,455,374.09342561 |
| Baseline A | 55.56682214560941 Hz | 18.657473129182723 Hz | 15.123469560352342 ms | 0.9255768830425335 ms | 41,266,896.0729927 |
| Baseline B | 57.13136189901428 Hz | 18.507342587004626 Hz | 14.064477577608749 ms | 0.8569736382968403 ms | 40,131,299.89084507 |
| Candidate B | 56.607534383097466 Hz | 18.536974287422762 Hz | 14.124118349287013 ms | 0.8779872078505246 ms | 40,387,337.81338028 |

- Ordering A: +2.5703735896551265 Hz and -1,811,521.9795670882 cycles/presentation.
- Ordering B: -0.523827515916814 Hz and +256,037.92253521085 cycles/presentation.
- Both candidate arms passed the authentic 18.206-Hz simulation gate. Ordering A won both mandatory metrics, but Ordering B lost both; the contradictory orderings were not averaged, synchronized fidelity and sustained screens were skipped, and Task #222 production was restored byte-exactly.
- The experimental common-Lino helper retained the exact 64 restoring decisions but replaced 256 four-word radicand shifts with 64 dynamic active-limb shifts, 64 pointer reads, and three boundary advances. A 65,548-case normalized model, 92,146-case binary64 model, 4,096 public-state cases, and one adversarial semantic review all passed, including the accepted private equality-borrow residual quirk.
- Generated-layout proof confined all 722 changed byte values to the exact 1,112-byte root helper island `[0x256f1,0x25b49)`. The 29-byte unreachable shared-Lino calibration preserved the endpoint and every downstream address/byte; no architecture-specific source, raw target-machine block, compiler change, or CPU-pack change was introduced.
- Restored shared-Lino source: `work/fp/fpsoft.txt`, SHA-256 `6b2e209be5b62013276514f8c418cafc92ecb9fd4d9fd6fbdf91453bfebe66d3`.
- Restored executable: `c4a62f5068262239a8a5665c443a75784fa2472941c9dfdb8fb731f5c8217ca2` (645,966 bytes).
- Evidence: `build/limb-pointer-restoring-fsqrt-20260830/result.json`; exact transform, model, adversarial review, private build, production layout, strict ABBA, restoration, and manifest proofs are retained in the same directory.

### Same-footprint exact fixed-F64 helper calls — Task #218

| Run | Presentation | Simulation | Render | Cycles/presentation |
|---|---:|---:|---:|---:|
| Candidate A | 48.76580373269115 Hz | 18.663455749548465 Hz | 18.865319865319865 ms | 46,918,247.29218107 |
| Baseline A | 39.328144203195414 Hz | 18.844735764031135 Hz | 23.94501025385212 ms | 58,166,118.161458336 |
| Baseline B | 42.92199752373091 Hz | 18.572018159306644 Hz | 22.006659801075728 ms | 53,559,344.495192304 |
| Candidate B | 35.808748728382504 Hz | 18.71820956256358 Hz | 26.30224159920151 ms | 63,698,736.46590909 |

- Ordering A: +9.437659529495733 Hz and -11,247,870.869277269 cycles/presentation.
- Ordering B: -7.1132487953484045 Hz and +10,139,391.97071679 cycles/presentation.
- All four runs passed the authentic simulation gate. Ordering A won both mandatory metrics, but Ordering B lost both; the contradictory orderings were not averaged and synchronized fidelity was skipped.
- Eleven exact shared-Lino call sites retained their accepted five-byte addresses and surrounding instructions. Only their 44 displacement bytes changed, targeting six **26-byte** helpers appended after the prior unreachable EOF padding; the package suffix remained byte-exact after the resulting **156-byte** shift.
- The accepted source and 645,966-byte executable were restored byte-exactly. Evidence: `build/fixed-f64-helper-calls-20260830/result.json`.

### Same-size in-place marked layer-copy repack — Task #175

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | 38.45414343395501 Hz | 18.842530282637956 Hz | 24.325050561173462 ms | 19.32901989109901 ms | 1.6040976775197244 ms | 58,049,964.38 |
| Baseline A | 35.74313408723748 Hz | 18.780290791599352 Hz | 26.29869022430709 ms | 20.72581928433565 ms | 1.5765246833171447 ms | 63,909,043.265536726 |
| Baseline B | 37.990196078431374 Hz | 18.790849673202615 Hz | 24.87432376420754 ms | 19.538711354532037 ms | 1.439308286853353 ms | 60,057,086.05913979 |
| Candidate B | 36.915504511894994 Hz | 18.252666119770304 Hz | 25.137509889729518 ms | 19.74712023438659 ms | 1.686747762448697 ms | 61,973,446.516666666 |

- Ordering A: +2.711009346717532 Hz and -5,859,078.885536723 cycles/presentation.
- Ordering B: -1.07469156653638 Hz and +1,916,360.4575268775 cycles/presentation.
- Candidate A passed the 18.206-Hz simulation gate by 0.6365302826379562 Hz. Ordering A won both mandatory metrics, but Ordering B lost both; the contradictory orderings were not averaged and synchronized fidelity was skipped.
- The shared scalar Lino loop and its zero-byte marker remained byte-exact. The fail-closed i386m compiler replacement removed a three-byte preheader no-op, used a short backedge around `[0x1a6c1,0x1a6cc)`, and moved an equivalent seven-byte CS-prefixed LEA to the once-per-row exit `[0x1a6cc,0x1a6d3)`.
- The 2,564-case ordered overlap model, 28 explicit modular-wrap cases, one positive and six byte-identical negative fixtures, 26-check toolchain regression, zero-warning three-stage compiler fixpoint, and full production-layout proof passed. Exactly 18 byte values changed inside the same 23-byte island; existing pops, every downstream byte and address, the 645,966-byte executable, and the CPU pack remained exact. The full-frame model retained instruction and memory traffic counts while reducing dynamic encoded-byte demand by 1,022,400 bytes.
- Task #167 compiler, shared source, test, CPU pack, and executable were restored byte-exactly. The retained healthy absolute record and its 0.19331453886427852-Hz measured gap remain unchanged.
- Evidence: `build/in-place-layer-repack-20260829/result.json`; source, semantic, fixture, fixpoint, layout, ABBA, and storage proofs are retained in the same directory.

### Marked palette-address displacement fold — Task #169

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | 50.200803212851405 Hz | 18.674698795180724 Hz | 17.8089501830689 ms | 13.944154887384888 ms | 1.034095195828248 ms | 45,636,233.82 |
| Baseline A | 37.81773093614383 Hz | 18.805538334366606 Hz | 24.81988840827305 ms | 19.58173276144088 ms | 1.4794288345267954 ms | 60,677,928.57377049 |
| Baseline B | 44.699610416239494 Hz | 18.864055771990976 Hz | 21.035356567042186 ms | 16.538932225050907 ms | 1.2387797614801197 ms | 51,194,475.1880734 |
| Candidate B | 37.34524051146742 Hz | 19.07854678303227 Hz | 25.307361500506012 ms | 19.942022327459725 ms | 1.4592206694848366 ms | 61,157,850.61413044 |

- Ordering A: +12.383072276707573 Hz and -15,041,694.753770493 cycles/presentation.
- Ordering B: -7.354369904772071 Hz and +9,963,375.42605704 cycles/presentation.
- Candidate A passed the 18.206-Hz simulation gate by 0.46869879518072466 Hz. Ordering A won both mandatory metrics, but Ordering B lost both; the contradictory orderings were not averaged and synchronized fidelity was skipped.
- One zero-byte shared-Lino marker selected a fail-closed i386m compiler lowering for the exact always-run palette-compose island. The lowering replaced four `ADD EAX,pal` instructions with equivalent palette-load displacements, leaving all four scalar source additions and stores in shared Lino and preserving 128,000 dword loads, 64,000 ordered stores, and 768,000 bytes of core memory traffic per presentation.
- The 100,000-case modular address proof, complete 64,000-store frame trace, four overlap/wrap cases, one positive and six fail-closed negative fixtures, 28-check toolchain regression, zero-warning three-stage compiler fixpoint, and production disassembly/layout proof passed. Exactly 140 byte values changed inside `[0x771ef,0x77297)`; all downstream bytes and addresses remained exact, and the replacement retained 20 unreachable NOP bytes to preserve the 645,966-byte executable layout.
- Task #167 compiler, shared source, test, and executable were restored byte-exactly. The retained healthy absolute record and its 0.19331453886427852-Hz measured gap remain unchanged.
- Evidence: `build/palette-address-fold-20260829/result.json`; source, semantic, fixture, and layout proofs are retained in the same directory.

### Cold recorder-backedge padding relocation — Task #159

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | 40.832666132906326 Hz | 19.01521216973579 Hz | 23.11632556122794 ms | 18.27440685130592 ms | 1.3080505677101377 ms | 55,840,317.813725494 |
| Baseline A | 38.0057212913772 Hz | 18.79852881078872 Hz | 24.813228165074896 ms | 19.54111667043807 ms | 1.470065239280536 ms | 60,095,354.52150538 |
| Baseline B | 47.283702213279675 Hz | 18.712273641851105 Hz | 19.615076664417057 ms | 15.41256988598018 ms | 1.1293366011911103 ms | 48,488,203.61276596 |
| Candidate B | 39.243027888446214 Hz | 18.92430278884462 Hz | 24.060313987823807 ms | 18.96976959430957 ms | 1.3725263760049649 ms | 58,023,277.47715736 |

- Ordering A: +2.8269448415291265 Hz and -4,255,036.707779884 cycles/presentation.
- Ordering B: -8.04067432483346 Hz and +9,535,073.864391401 cycles/presentation.
- The candidate preserved every semantic operation and the 645,966-byte executable layout. Exactly 33 bytes changed inside the two proved backedge islands; no direct jump enters the relocated padding, and all other executable bytes remained exact.
- Candidate A passed the simulation gate. Ordering B then lost both mandatory metrics, so the contradictory orderings were not averaged, synchronized fidelity was skipped, and Task #153 source, test, compiler, CPU pack, and executable were restored byte-exactly.
- Evidence: `build/cold-recorder-padding-20260829/result.json`; source and layout proofs: `model.json` and `production-layout.json` in the same directory.

### Fixed-offset culling-scratch replay — Task #129

| Run | Presentation | Simulation | Render | Terrain | Present | Cycles/presentation |
|---|---:|---:|---:|---:|---:|---:|
| Candidate A | 51.250258317834266 Hz | 18.805538334366606 Hz | 18.03740967204002 ms | 14.17082294823289 ms | 1.0191598379027775 ms | 44,871,593.74596774 |
| Baseline A | 44.367909238249595 Hz | 18.638573743922205 Hz | 21.18756964319859 ms | 16.730832492669872 ms | 1.1748656079632513 ms | 51,420,790.89954338 |
| Baseline B | 46.69887278582931 Hz | 18.51851851851852 Hz | 20.045023842014075 ms | 15.72910182303246 ms | 1.181150913816102 ms | 48,833,549.051724136 |
| Candidate B | 39.967539054574964 Hz | 18.867924528301888 Hz | 23.6057060696197 ms | 18.622526545935273 ms | 1.388293517961408 ms | 57,109,637.51269036 |

- Ordering A: +6.882349079584671 Hz and -6,549,197.153575644 cycles/presentation.
- Ordering B: -6.731333731254345 Hz and +8,276,088.460966222 cycles/presentation.
- The candidate preserved simulation and passed exact source/model, private-build, and same-size isolated-tail layout checks.
- Ordering B lost both mandatory metrics, so the contradictory orderings were not averaged, synchronized fidelity was skipped, and Task #127's exact source, test, and executable checkpoint was restored.
- Evidence: `build/fixed-culling-scratch-replay-20260828/result.json`.

### Deferred terrain terminal-state loads — Task #92

| Run | Presentation | Simulation | Terrain | Cycles/presentation |
|---|---:|---:|---:|---:|
| Candidate A | 50.151668351870576 Hz | 18.6046511627907 Hz | 13.201962889747506 ms | 45,825,641.14516129 |
| Baseline A | 46.24159706661234 Hz | 18.741087797922184 Hz | 15.748775603895407 ms | 49,425,647.339207046 |
| Baseline B | 50.46535677352637 Hz | 18.200620475698035 Hz | 14.479662095832703 ms | 45,414,039.15983607 |
| Candidate B | 50.40816326530612 Hz | 18.775510204081634 Hz | 14.62135733079178 ms | 45,510,665.83805668 |

- Ordering A: +3.9100712852582333 Hz and -3,600,006.1940457523 cycles/presentation.
- Ordering B: -0.05719350822025149 Hz and +96,626.67822061479 cycles/presentation.
- Disposition: rejected after Ordering B; fidelity skipped; accepted production restored.
- Evidence: `build/deferred-terrain-state-20260828/result.json`.

### Aligned direct-B replay plus combined backedge — Task #117

| Run | Presentation | Simulation | Terrain | Cycles/presentation |
|---|---:|---:|---:|---:|
| Candidate A | 50.47445992327882 Hz | 18.776499091459723 Hz | 14.657139485695202 ms | 45,312,986.212 |
| Baseline A | 47.55216693418941 Hz | 18.65971107544141 Hz | 15.61580252264016 ms | 47,872,862.84388185 |
| Baseline B | 49.91883116883117 Hz | 18.66883116883117 Hz | 14.488042001649005 ms | 45,917,869.63414634 |
| Candidate B | 48.52579852579853 Hz | 18.632268632268634 Hz | 15.197821258989354 ms | 47,261,369.75949367 |

- Ordering A: +2.9222929890894136 Hz and -2,559,876.6318818554 cycles/presentation.
- Ordering B: -1.3930326430326403 Hz and +1,343,500.1253473312 cycles/presentation.
- The candidate kept the executable at 646,594 bytes, aligned the shortened 34-byte replay body at `0x2fa40`, and preserved every downstream code byte and offset.
- Disposition: rejected after Ordering B; fidelity skipped; accepted production restored.
- Evidence: `build/replay-aligned-combined-backedge-20260828/result.json`.

### Aligned unchanged accepted replay loop — Task #123

| Run | Presentation | Simulation | Terrain | Cycles/presentation |
|---|---:|---:|---:|---:|
| Candidate A | 57.587391392200445 Hz | 18.58961406344716 Hz | 10.003472124756335 ms | 39,834,633.7368421 |
| Baseline A | 46.60754794803052 Hz | 18.972984120437204 Hz | 16.01636036106982 ms | 49,317,372.876106195 |
| Baseline B | 59.441973311767086 Hz | 18.60088960776385 Hz | 9.89368199647547 ms | 38,665,362.67687075 |
| Candidate B | 45.98845311566793 Hz | 18.713915986462272 Hz | 16.250577849711473 ms | 49,563,368.65800866 |

- Ordering A: +10.979843444169923 Hz and -9,482,739.139264092 cycles/presentation.
- Ordering B: -13.453520196099156 Hz and +10,898,005.981137909 cycles/presentation.
- The candidate inserted the cold 11-byte `A = 0; B + 0;` prefix and moved the unchanged accepted 47-byte loop from `0x2fa35` to `0x2fa40`. Executable size and every later instruction byte and offset were preserved.
- Host conditions crossed sharply between runs. The per-ordering gates reject rather than average the contradictory result; fidelity was skipped and accepted production was restored exactly.
- Baseline B is separately classified as a healthy-host absolute observation of the unchanged accepted executable and establishes the 59.441973311767086-Hz production record above.
- Evidence: `build/replay-aligned-accepted-loop-20260828/result.json`.

## Rejected Ordering-A candidates

All candidates in this table passed Candidate A's 18.206-Hz simulation gate, then lost either or both required Ordering-A metrics. Reverse ordering and fidelity were skipped.

| Experiment | Candidate / Baseline presentation | Candidate simulation | Candidate / Baseline cycles/presentation | Candidate delta | Evidence |
|---|---:|---:|---:|---|---|
| Register-resident odd-trial restoring root, Task #226 | 53.00713557594292 / 56.45645645645646 Hz | 18.75637104994903 Hz | 43,331,349.30384615 / 40,524,461.95390071 | -3.4493208805135396 Hz; +2,806,887.349945441 cycles | `build/register-trial-restoring-fsqrt-20260830/result.json` |
| Packed terrain thresholds, Task #79 | 47.227926078028744 / 54.973821989528794 Hz | 18.8911704312115 Hz | 48,448,103.17826087 / 41,751,507.307692304 | -7.74589591150005 Hz; +6,696,595.870568566 cycles | `build/packed-depth-threshold-20260828/result.json` |
| Bounded ground tint masks, Task #87 | 42.29668982427462 / 55.53327987169206 Hz | 19.0028606456886 Hz | 53,941,235.801932365 / 41,182,185.85198556 | -13.236590047417437 Hz; +12,759,049.949946806 cycles | `build/ground-tint-mask-20260828/result.json` |
| Early wide-Z denominator handoff, Task #89 | 38.508309687880015 / 40.55714870954527 Hz | 18.646128901499797 Hz | 59,530,025.510526314 / 56,560,368.78282829 | -2.048839021665252 Hz; +2,969,656.727698028 cycles | `build/early-z-handoff-20260828/result.json` |
| Fixed-slot exact terrain rotation, Task #90 | 56.477732793522264 / 57.54962903549228 Hz | 18.62348178137652 Hz | 40,620,539.15412186 / 39,874,447.452961676 | -1.0718962419700162 Hz; +746,091.701160185 cycles | `build/fixed-terrain-rotate-20260828/result.json` |
| Monotone terrain map index, Task #94 | 43.14204314204314 / 50.733496332518335 Hz | 18.72201872201872 Hz | 52,992,789.344339624 / 45,220,363.59437751 | -7.5914531904751925 Hz; +7,772,425.749962114 cycles | `build/monotone-terrain-map-index-20260828/result.json` |
| Direct-threaded terrain depth, Task #96 | 48.690671031096564 / 52.17036886081109 Hz | 18.821603927986907 Hz | 47,084,223.51680672 / 44,026,362.83984375 | -3.4796978297145245 Hz; +3,057,860.6769629717 cycles | `build/direct-threaded-terrain-depth-20260828/result.json` |
| Accounted i386m multiply-by-18, Task #103 | 35.32277710109622 / 41.11270198404582 Hz | 18.879415347137638 Hz | 64,614,391.82183908 / 55,515,525.323383085 | -5.789924882949599 Hz; +9,098,866.498455994 cycles | `build/i386m-fixed-mul18-codegen-20260828/result-accounted.json` |
| Unpadded replay register retention, Task #105 | 35.823950870010236 / 36.221444741716404 Hz | 19.037871033776867 Hz | 63,831,594.58857143 / 63,088,209.1875 | -0.39749387170616757 Hz; +743,385.4010714293 cycles | `build/replay-register-retention-20260828/result.json` |
| Layout-stable register-nonzero branches, Task #114 | 34.328661385334144 / 34.688013136289 Hz | 18.281535648994517 Hz | 65,983,452.964497045 / 65,931,137.1183432 | -0.3593517509548556 Hz; +52,315.84615384787 cycles | `build/compare-zero-backedge-20260828/result.json` |
| Direct-B absolute replay pointer, Task #115 | 34.16717510677242 / 36.87590636005801 Hz | 18.91397193410616 Hz | 66,846,338.678571425 / 62,043,054.38764045 | -2.70873125328559 Hz; +4,803,284.290930979 cycles | `build/replay-direct-b-pointer-20260828/result.json` |
| 64-byte-aligned relative replay plus combined backedge, Task #118 | 39.183673469387756 / 39.398862713241265 Hz | 18.775510204081634 Hz | 58,265,913.578125 / 57,233,087.938144326 | -0.21518924385350857 Hz; +1,032,825.6399806738 cycles | `build/replay-aligned-relative-backedge-20260828/result.json` |
| Layout-stable indexed replay loads, Task #120 | 58.859223300970875 / 59.294871794871796 Hz | 18.6084142394822 Hz | 38,921,432.501718216 / 38,649,322.01689189 | -0.43564849390092064 Hz; +272,110.48482632637 cycles | `build/replay-indexed-loads-20260828/result.json` |
| Exact marked i386m replay LEA, Task #121 | 45.85286325657224 / 55.47652916073969 Hz | 18.54493580599144 Hz | 49,998,154.72 / 41,303,399.43956044 | -9.623665904167446 Hz; +8,694,755.280439556 cycles | `build/marked-replay-lea-20260828/result.json` |
| Fixed three-point projected terrain bounds, Task #131 | 33.93337471549762 / 37.47696088470203 Hz | 18.208152286364577 Hz | 67,581,555.93292683 / 60,840,425.01092896 | -3.54358616920441 Hz; +6,741,130.921997875 cycles | `build/fixed-terrain-bounds-unroll-20260828/result.json` |
| Generalized layout-stable i386m immediate multiply, Task #135 | 37.580012389015074 / 42.69160398454971 Hz | 18.996489779062564 Hz | 60,807,975.74725275 / 53,502,475.53333333 | -5.111591595534634 Hz; +7,305,500.213919416 cycles | `build/i386m-general-immediate-mul-codegen-20260828/result.json` |
| Combined paired culling-replay cursor add, Task #138 | 59.895833333333336 / 59.53322784810127 Hz | 18.42948717948718 Hz | 38,259,826.39464883 / 38,147,040.06312292 | +0.36260548523206637 Hz; +112,786.33152590692 cycles | `build/paired-replay-cursor-add-20260828/result.json` |
| Combined culling-pair decrement/backedge, Task #143 | 36.87196110210697 / 38.36416747809153 Hz | 19.043760129659642 Hz | 62,204,724.807692304 / 59,132,669.87309644 | -1.4922063759845585 Hz; +3,072,054.9345958605 cycles | `build/combined-pair-backedge-20260828/result.json` |
| Exact i386m low-16 mask code generation, Task #147 | 38.78514262261441 / 39.02439024390244 Hz | 18.674327929406935 Hz | 59,098,001.015873015 / 58,652,515.223958336 | -0.23924762128802968 Hz; +445,485.7919146791 cycles | `build/i386m-low16-mask-codegen-20260828/result.json` |
| Exact i386m register signed-imm8 code generation, Task #151 | 38.57201477226098 / 56.88924752874723 Hz | 18.26015592942142 Hz | 58,893,319.7180851 / 39,903,896.75177305 | -18.31723275648625 Hz; +18,989,422.96631205 cycles | `build/i386m-register-imm8-codegen-20260828/result.json` |
| Exact adjacent i386m byte-load fold, Task #155 | 54.989816700611 / 58.62412761714855 Hz | 18.73727087576375 Hz | 41,634,715.29259259 / 39,013,316.76190476 | -3.634310916537551 Hz; +2,621,398.5306878313 cycles | `build/i386m-adjacent-byte-load-codegen-20260829/result.json` |
| Compact shared-Lino culling-pair stream, Task #157 | 39.21174341443796 / 48.55144855144855 Hz | 18.499899457068167 Hz | 58,248,139.9025641 / 46,885,587.38271605 | -9.33970513701059 Hz; +11,362,552.519848049 cycles | `build/compact-culling-pair-stream-20260829/result.json` |
| Live-register repeating recorder command publication, Task #161 | 39.25455987311658 / 40.4659717964439 Hz | 18.834258524980175 Hz | 58,068,348.42929293 / 56,317,269.015151516 | -1.2114119233273257 Hz; +1,751,079.4141414165 cycles | `build/register-command-publication-20260829/result.json` |
| Exact marked i386m `REP MOVSD` layer copy, Task #165 | 39.25577591494582 / 55.645161290322584 Hz | 18.810059292578206 Hz | 58,138,933.354166664 / 41,158,409.00362319 | -16.38938537537676 Hz; +16,980,524.350543477 cycles | `build/exact-rep-layer-copy-20260829/result.json` |
| Exact marked GUI counter-tail DEC/JNE fusion, Task #171 | 47.33253108704372 / 56.09955120359037 Hz | 18.852787805856398 Hz | 48,264,145.165254235 / 40,884,152.410909094 | -8.767020116546654 Hz; +7,379,992.754345141 cycles | `build/gui-tail-fusion-20260829/result.json` |
| Exact marked four-way i386m layer-copy appendix, Task #173 | 37.92134831460674 / 49.797570850202426 Hz | 18.86035313001605 Hz | 58,621,794.82539683 / 45,961,850.75203252 | -11.876222535595687 Hz; +12,659,944.07336431 cycles | `build/four-way-delta-layer-copy-20260829/result.json` |
| Block-index-controlled GUI backedges, Task #183 | 38.079805549929105 / 41.68377823408624 Hz | 18.229694146242657 Hz | 60,224,177.595744684 / 54,996,171.26600985 | -3.603972684157135 Hz; +5,228,006.329734832 cycles | `build/gui-block-index-backedge-20260829/result.json` |
| Final-row-only GUI physical-base demotions, Task #187 | 59.94716521032311 / 60.15187849720224 Hz | 18.49217638691323 Hz | 38,403,475.08813559 / 38,184,297.03654485 | -0.2047132868791337 Hz; +219,178.05159074068 cycles | `build/gui-deferred-demotions-20260829/result.json` |
| Exact rooted resident selection with squared rejection, Task #207 | 60.07281553398058 / 60.08328375966686 Hz | 18.6084142394822 Hz | 38,219,907.99663299 / 37,916,414.0 | -0.010468225686281585 Hz; +303,493.9966329932 cycles | `build/squared-resident-selection-20260829/result.json` |
| Exact raw local-renderer FP constants, Task #217 | 55.72755417956656 / 55.90312815338042 Hz | 18.988648090815275 Hz | 41,224,026.492592596 / 40,954,133.981949456 | -0.17557397381386153 Hz; +269,892.5106431395 cycles | `build/exact-local-fp-constants-20260830/result.json` |
| Dead local-renderer fixed-F64 FI/conversion stores, Task #219 | 36.50220617729643 / 38.91977760127085 Hz | 18.852787805856398 Hz | 62,162,241.472527474 / 58,692,867.14285714 | -2.4175714239744224 Hz; +3,469,374.3296703324 cycles | `build/dead-fixed-f64-fi-stores-20260830/result.json` |
| Direct fixed-LOD p64/p53 scalar multiplies, Task #220 | 58.47953216374269 / 53.054662379421224 Hz; reverse 45.73972879983809 / 52.36857885268839 Hz | 18.552127445049404 / 18.619712608783647 Hz | 39,077,793.69310345 / 43,219,063.003787875; reverse 49,567,453.82743363 / 43,630,434.7519084 | Ordering A +5.424869784321466 Hz, -4,141,269.3106844276 cycles; Ordering B -6.6288500528502965 Hz, +5,937,019.075525232 cycles | `build/direct-lod-scalar-mul-20260830/result.json` |
| Same-epoch exact local geometry replay, Task #209 | 60.17017828200972 / 58.2010582010582 Hz; reverse 43.689320388349515 / 58.66935483870968 Hz | 18.638573743922205 / 18.810679611650485 Hz | 38,126,355.34680135 / 39,437,279.58041958; reverse 52,157,797.449074075 / 39,090,568.962199315 | Ordering A +1.9691200809515195 Hz, -1,310,924.2336182296 cycles; Ordering B -14.980034450360165 Hz, +13,067,228.48687476 cycles | `build/local-geometry-replay-20260829/result.json` |
| Same-second exact absolute orbital body-state cache, Task #210 | 34.97740224012576 / 28.261314765513003 Hz; reverse 27.45995423340961 / 34.355828220858896 Hz | 18.667714678718806 / 18.0986061992927 Hz | 64,763,099.56741573 / 80,031,064.97826087; reverse 82,506,951.9090909 / 66,075,453.14285714 | Ordering A +6.71608747461276 Hz, -15,267,965.410845146 cycles; Ordering B -6.895873987449285 Hz, +16,431,498.766233765 cycles; Candidate B simulation failed | `build/orbital-vector-cache-20260829/result.json` |

Task #155's Candidate A reduced the executable from 645,966 to 645,886 bytes through 12 exact `D = [A]; D & 255` and four exact `E = [D]; E & 255` folds. Its terrain time also lost by 2.051949297617302 ms. The 18.206-Hz simulation gate passed, but both mandatory Ordering-A metrics failed, so Ordering B and synchronized fidelity were not run. Production was restored byte-exactly to Task #153 (`fd0f7912d2ebe84b3fdea8a759f1226465d5516a6965ed01faec94e1aa5985d2` game; `04e98c971c4f61002529ed5a3b0a1c1587288a9b7ad30fcad19228286edb77de` compiler). Semantic and layout proofs remain in `build/i386m-adjacent-byte-load-codegen-20260829/fixture-semantics.json` and `build/i386m-adjacent-byte-load-codegen-20260829/production-layout.json`; the complete disposition is in `build/i386m-adjacent-byte-load-codegen-20260829/result.json`.

Task #157's Candidate A retained one physical command word for each adjacent equal-value culling pair while preserving two logical ordered stores. The exhaustive **16,776,960-case** encoding proof, 15 stream/cursor model cases, and generated-layout proof all passed with zero unexpected changed bytes and an unchanged 645,966-byte executable. Terrain time nevertheless lost by **3.6637190327539564 ms**, and both mandatory Ordering-A metrics failed. Ordering B and synchronized fidelity were therefore not run. Production was restored byte-exactly to Task #153 (`fd0f7912d2ebe84b3fdea8a759f1226465d5516a6965ed01faec94e1aa5985d2` game; unchanged `04e98c971c4f61002529ed5a3b0a1c1587288a9b7ad30fcad19228286edb77de` compiler). Proofs remain in `build/compact-culling-pair-stream-20260829/model.json` and `build/compact-culling-pair-stream-20260829/production-layout.json`; the complete disposition is in `build/compact-culling-pair-stream-20260829/result.json`.

Task #161's Candidate A retained all six `PGtrval` stores while changing only the two repeating producers to use a live value register and one `PGtrused` read. The exhaustive **16,777,216-case** encoding proof, 1,728 stream/state cases, and generated-layout proof passed with zero unexpected changed bytes and an unchanged 645,966-byte executable. Terrain time nevertheless lost by **1.0807228023402224 ms**, and both mandatory Ordering-A metrics failed. Ordering B and synchronized fidelity were therefore not run. Production was restored byte-exactly to Task #153 (`fd0f7912d2ebe84b3fdea8a759f1226465d5516a6965ed01faec94e1aa5985d2` game; unchanged `04e98c971c4f61002529ed5a3b0a1c1587288a9b7ad30fcad19228286edb77de` compiler). Proofs remain in `build/register-command-publication-20260829/model.json` and `build/register-command-publication-20260829/production-layout.json`; the complete disposition is in `build/register-command-publication-20260829/result.json`.

Task #165's candidate used one zero-byte shared-Lino marker and a guarded i386m compiler lowering to replace only the exact scalar copy body at `[0x1a6bc,0x1a6d3)` with same-size `PUSHFD`/ESI/EDI preservation, forced-displacement LEAs, `CLD`, and `REP MOVSD`. The 20-case overlap/store-order model, one positive and six negative compiler fixtures, 26-check toolchain regression, compiler self-host fixpoint, and production-layout proof all passed; exactly 21 byte values changed and every downstream byte and address remained exact. Candidate A passed the simulation gate by **0.6040592925782065 Hz**, but terrain time rose from **11.514370049596565 ms** to **18.873720446058858 ms** and it lost both mandatory Ordering-A metrics. Ordering B and synchronized fidelity were therefore not run. Production was restored byte-exactly to Task #153 (`fd0f7912d2ebe84b3fdea8a759f1226465d5516a6965ed01faec94e1aa5985d2` game; `04e98c971c4f61002529ed5a3b0a1c1587288a9b7ad30fcad19228286edb77de` compiler; unchanged `1dd1433597c42e30b13bd55bfd02c19ebe465f3e020e4878906f66e7bfcdc4b7` CPU pack). Proofs remain in `build/exact-rep-layer-copy-20260829/model.json` and `build/exact-rep-layer-copy-20260829/production-layout.json`; the complete disposition is in `build/exact-rep-layer-copy-20260829/result.json`. The retained healthy-host record remains **59.80668546113572 Hz**.

Task #171 used two zero-byte shared-Lino markers and exact fail-closed i386m lowerings to remove the reload and zero comparison after each always-run `VHGUIx` decrement. The 100,007-case 32-bit DEC/ZF proof, complete 32,000-tail counter/branch trace, one positive and eight per-island fail-closed fixtures, 28-check toolchain regression, three-stage compiler fixpoint, and exact two-island production-layout proof passed. Exactly 86 byte values changed inside `[0x771ef,0x77297)` and `[0x77401,0x774d3)`; eleven unreachable NOP bytes per island preserved the 645,966-byte layout and every downstream address. Candidate A passed the simulation gate by **0.6467878058563983 Hz**, but render time rose from **14.684919215496073 ms** to **19.925152531084734 ms** and both mandatory Ordering-A metrics lost. Ordering B and synchronized fidelity were skipped, and Task #167 compiler, shared source, tests, CPU pack, and executable were restored byte-exactly. Proofs and the complete disposition remain in `build/gui-tail-fusion-20260829/`; the retained healthy absolute record remains **59.80668546113572 Hz**.

Task #173 kept the shared scalar layer-copy loop byte-for-byte unchanged, added one shared zero-byte EOF label, and used an exact fail-closed i386m compiler lowering to replace only `[0x1a6bc,0x1a6d3)` with a jump stub. The candidate appendix at `[0x9b0da,0x9b11e)` used a four-dword path for counts divisible by four and an ordered scalar fallback otherwise, then returned both paths to the unchanged pops at `0x1a6d3`. The **2,564-case** ordered overlap model, 10,000 modular address identities, 28 explicit wrap cases, one positive and six byte-identical negative fixtures, 27-check candidate toolchain regression, three-stage compiler fixpoint, and full production-layout proof passed. The candidate grew by exactly 68 bytes to 646,034 bytes; only 28 bytes changed within the accepted-length prefix, and the 10,866-byte post-code payload shifted byte-exactly. Candidate A passed the simulation gate by **0.6543531300160517 Hz**, but terrain time rose from **14.63095460531601 ms** to **19.063358671866002 ms** and both mandatory Ordering-A metrics lost. Ordering B and synchronized fidelity were skipped, and Task #167 compiler, shared source, tests, CPU pack, and executable were restored byte-exactly. Proofs and the complete disposition remain in `build/four-way-delta-layer-copy-20260829/`; the retained healthy absolute record remains **59.80668546113572 Hz**.

Task #183 left every shared-Lino source byte unchanged and refined only Task #180's two full candidate vectors. It preserved all 32,000 `VHGUIx` decrement writes and the exact 79-taken/one-fallthrough branch trace per row while replacing 32,000 counter reloads with `CMP EBX,320` against the already-live positive block index. The exact one-row counter/branch proof, taken/fallthrough flag-liveness proof, twelve byte-identical fail-closed negative fixtures, 28-check toolchain regression, zero-warning three-stage compiler fixpoint, and production disassembly/layout proof passed. Exactly 131 byte values changed inside `[0x771ef,0x77297)` and `[0x77401,0x774d3)`; all downstream bytes and addresses and the 645,966-byte layout remained exact. The model removed 32,000 instructions, 32,000 workspace dword reads, and 96,000 dynamically fetched encoded bytes per presentation with no new stack traffic. Candidate A passed the simulation gate by **0.023694146242657865 Hz**, but render time rose from **22.64255683728594 ms** to **24.75834465486077 ms**, presentation lost **3.603972684157135 Hz**, and cycles/presentation increased by **5,228,006.329734832**. Ordering B and synchronized fidelity were skipped, and Task #180 source, tests, compiler, CPU pack, and executable were restored byte-exactly. Proofs and the complete disposition remain in `build/gui-block-index-backedge-20260829/`; the retained healthy absolute record and its **0.19331453886427852-Hz** measured gap remain unchanged.

Task #187 left both shared-Lino marker islands and every shared source operation byte-exact while changing only Task #185's two full fail-closed i386m vectors. It moved six compose and nine fixed-2x physical-base demotion instructions from each hot outer-row tail to the single final-row fallthrough, then repeated `CMP EAX,200` to restore exact terminal flags. The model preserved every workspace load/store, inner and outer counter trace, pixel event, branch decision, logical terminal register, existing private stack-operation address/count, and final ESP; the taken-edge D spill value is compiler-private and dead before semantic use. Twelve byte-identical negative fixtures, the 28-check toolchain regression, zero-warning three-stage compiler fixpoint, and complete disassembly/layout proof passed. Exactly 122 byte values changed inside `[0x771ef,0x77297)` and `[0x77401,0x774d3)`, with zero unexpected changes; the model removed 2,983 instructions and 10,935 dynamically fetched encoded bytes per presentation. Candidate A passed simulation by **0.28617638691322966 Hz** and reached an experimental **59.94716521032311 Hz**, but lost both Ordering-A metrics, so Ordering B and fidelity were skipped and Task #185 production was restored byte-exactly. The unchanged production Baseline A independently reached **60.15187849720224 Hz** at **18.585131894484412-Hz** simulation, establishing the first healthy fixed-discriminator result above target. Proofs and the complete disposition remain in `build/gui-deferred-demotions-20260829/`.

## Candidate-A simulation-gate failures

Baseline A, Ordering B, and fidelity were skipped under the binding stop rule.

| Experiment | Candidate presentation | Candidate simulation | Terrain | Cycles/presentation | Evidence |
|---|---:|---:|---:|---:|---|
| Pure-Lino dual publication, Task #70 | 40.479140850888065 Hz | 18.174308137133416 Hz | Not retained in summary | 56,692,015.81122449 | `build/pure-lino-dual-publication-20260827/result.json` |
| Layout-stable i386m multiply-by-320, Task #100 | 36.4405073485001 Hz | 18.11958928930944 Hz | 20.48425306637529 ms | 62,548,029.81767956 | `build/i386m-fixed-mul320-codegen-20260828/result.json` |
| Absolute replay stream pointer in A, Task #108 | 34.63203463203463 Hz | 18.140589569160998 Hz | 21.13248357827206 ms | 65,268,425.14880952 | `build/replay-absolute-pointer-20260828/result.json` |
| Combined replay decrement/backedge, Task #110 | 37.98994974874372 Hz | 18.09045226130653 Hz | 19.53835273995132 ms | 60,143,173.4021164 | `build/replay-combined-backedge-20260828/result.json` |
| 64-byte-aligned direct-B replay pointer, Task #116 | 36.880290205562275 Hz | 18.137847642079805 Hz | 20.01978055772834 ms | 61,625,879.96721312 | `build/replay-aligned-b-pointer-20260828/result.json` |
| Mirrored palette-compose/fixed-2x GUI counters, Task #163 | 40.641934139224674 Hz | 18.132555231346394 Hz | 18.11189620348499 ms | 56,621,254.78974359 | `build/mirrored-gui-counters-20260829/result.json` |
| Exact negative-index/end-pointer i386m layer copy, Task #177 | 35.044320758606474 Hz | 18.140589569160998 Hz | 21.16365851905574 ms | 64,858,797.92941176 | `build/negative-index-layer-copy-20260829/result.json` |
| Deferred exact orbital terminal down-y replay, Task #212 | 31.978543428925107 Hz | 18.155560140292966 Hz | 28.615505563097525 ms render | 68,267,842.58064516 | `build/deferred-orbital-terminal-replay-20260829/result.json` |
| Local static orbital-rate root cache, Task #216 | 32.19814241486068 Hz | 18.163054695562437 Hz | 29.240459136665613 ms render | 69,809,969.87820514 | `build/local-orbital-rate-cache-20260830/result.json` |

Task #163's pure shared-Lino candidate kept B live across both 80x200 loops while publishing the exact accepted `VHGUIx` trace `80,79,...,0` on every row. Complete event-by-event models preserved all 32,400 counter stores, 64,000 palette-compose stores, 256,000 fixed-2x Backdrop stores, and final `VHGUIx=0` / `VHGUIy=200` state. Production disassembly confined all 301 changed bytes to `[0x771e5,0x77297)` and `[0x773f7,0x774d3)`, preserved the 645,966-byte layout and all downstream offsets, and proved no direct jump enters the two three-byte unreachable padding suffixes. Candidate A nevertheless missed the authentic simulation gate by **0.07344476865360505 Hz**, so no baseline comparison or fidelity conclusion was admitted. Task #153 source, tests, compiler, CPU pack, and executable were restored byte-exactly; proofs remain in `build/mirrored-gui-counters-20260829/model.json` and `production-layout.json`, with the complete disposition in `result.json`.

Task #177 left the shared scalar layer-copy loop and zero-byte marker unchanged and replaced only the exact 23-byte i386m island at `[0x1a6bc,0x1a6d3)`. The candidate formed source and destination end pointers, used one increasing negative index for both exact left-to-right addresses, and reduced the scalar loop to nine encoded bytes. The **2,564-case** ordered overlap model, 28 explicit modular-wrap cases, symbolic zero-count identity, post-pop flag proof, one positive and six byte-identical negative fixtures, 26-check toolchain regression, three-stage compiler fixpoint, and production-layout proof passed. Exactly 22 byte values changed; the existing pops, every downstream byte and address, 645,966-byte executable, and CPU pack remained exact. The full-frame model removed an estimated **254,800 instructions** and **1,533,600 dynamically fetched encoded bytes** while retaining all 256,000 loads, stores, and branches. Candidate A nevertheless produced only **18.140589569160998-Hz simulation**, missing the binding gate by **0.06541043083900178 Hz**. Baseline A, Ordering B, and synchronized fidelity were skipped; Task #167 production was restored byte-exactly. Proofs and the complete disposition remain in `build/negative-index-layer-copy-20260829/`; the retained healthy absolute record remains **59.80668546113572 Hz**.

Task #212 retained Task #210's flat 640-unit, eight-word absolute-body records but reduced each hot hit from eight cached loads to six and conditionally restored only the latest terminal down-y pair once at common render exit. The **12,304-case** model preserved raw binary64 words, moving-camera subtraction, same-frame epoch failure, lifecycle invalidation, exact 80-body capacity, companion calls, and surface hit/miss topology. Adversarial review rejected an initial unmeasured build because it falsely invalidated pending state on surface misses; those calls do not access `VHGNDowny0/1`. The corrected model, semantic review, and private build passed, but Candidate A produced only **18.155560140292966-Hz simulation**, missing the gate by **0.05043985970703346 Hz**. The stop rule skipped every baseline, ordering, fidelity, and sustained stage; accepted source and executable were restored byte-exactly. Proofs and the complete disposition remain in `build/deferred-orbital-terminal-replay-20260829/`; the retained healthy absolute record remains **60.15187849720224 Hz**.

Task #216 reserved one eight-word pure shared-Lino record for each of 80 local bodies and published its valid word only after owner, scaled mass, orbit radius, and the exact static pre-time root were complete. The live `SUsec`, multiply/divide grouping, primary/moon `FS0`, body-vector suffix, FP/VHGND scratch, and terminal A-E state remained exact; out-of-range bodies and owners used the original helpers, and both generated-system entry paths cleared valid words before use. The **3,825-case** model and bounded semantic review passed, and the candidate built privately with **62 warnings, 0 errors**. Candidate A nevertheless produced only **18.163054695562437-Hz simulation**, missing the binding gate by **0.042945304437562726 Hz**. The stop rule skipped every baseline, ordering, fidelity, and sustained stage; accepted source and executable were restored byte-exactly. Proofs and the complete disposition remain in `build/local-orbital-rate-cache-20260830/`; the retained healthy absolute record remains **60.15187849720224 Hz**.

## Pre-timing and attribution results

These results informed optimization selection but are not candidate FPS measurements.

| Task | Result | Disposition | Evidence |
|---|---|---|---|
| #64, complete tile-admission/material stage attribution | 0.5796 ms/presentation; 95% CI 0.5473-0.6119; 18.899-Hz simulation | Below admission gates; no candidate | `build/tile-admission-diagnostic-20260827/result.json` |
| #66, exact viewport-mask body attribution | 0.3730 ms/presentation; 95% CI 0.3686-0.3774; 18.872-Hz simulation | Below admission gates; no candidate | `build/viewport-mask-diagnostic-20260827/result.json` |
| #69, leaf-call inlining screen | Full selected body had only a 0.71159-ms 95% upper bound | Call overhead necessarily smaller; no implementation | `build/leaf-inline-selection-20260827/result.json` |
| #102, initial i386m multiply-by-18 localization | Three substitutions found while only two source sites had been proved | Timing skipped; later accounted by Task #103 | `build/i386m-fixed-mul18-codegen-20260828/result.json` |
| #112, paired replay records | Candidate body was at least 30 generated bytes beyond the accepted downstream boundary | Exact-layout gate failed; timing skipped | `build/replay-paired-records-20260828/result.json` |
| #206, live orbital renderer attribution | `VHT render` 0 ms; active `VHG local render` 10.764073345590855 ms; selected-origin/resident scan 4.8364453509384 ms and largest narrowed star/setup subphase | Depressed-host instrumentation only; no candidate FPS conclusion; squared-distance resident selection chosen next | `build/live-space-render-attribution-20260829/result.json` |

## Publication rule

For every retained performance checkpoint, update this file in the same commit with:

1. production executable size and SHA-256;
2. healthy absolute result, or an explicit statement that it remains unchanged;
3. presentation and simulation rates;
4. render/terrain/presentation timing and cycles per presentation;
5. discriminator conditions and host classification;
6. ABBA deltas and synchronized fidelity disposition;
7. the local raw-report path and published commit identity when known.

Rejected trials that materially affect optimization selection should also be appended in their correct evidence class, without replacing retained records.
