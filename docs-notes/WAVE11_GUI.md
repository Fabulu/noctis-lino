# Wave 11 -- Stardrifter in an iGUI window

This is a later wave. It starts only after the authentic renderer and game loop
are stable and Wave 10 has joined the vehicle renderer to the rasteriser. The
deliverable is the complete game presented inside a Linoleum iGUI window, with
user-adjustable window dimensions and a picture that scales without changing
the game's aspect ratio.

## Product requirement

The game remains a graded 320×200 software framebuffer. It must be anchored in
an iGUI client window rather than opening as an unrelated display. The default
presentation is 8:5 (320:200), with nearest-neighbour enlargement and centered
letterboxing/pillarboxing as needed. A later presentation option may use a 4:3
viewport, but that is a display policy only: it must not change the simulation,
camera, projection, raster page, or the 320×200 oracle.

The intended pipeline is:

```
game loop → authentic 320×200 framebuffer → integer/nearest-neighbour aspect-fit
           → iGUI Backdrop Layer → Refresh Display / host window
```

Do not stretch the framebuffer to the current window rectangle. Compute the
largest destination rectangle with the selected aspect ratio, clear the unused
bars, and map each destination pixel to a source pixel using nearest-neighbour
sampling. Scaling must be deterministic and independent of host DPI or window
manager behaviour.

## Recon findings

The stock iGUI already supplies most window plumbing:

* `main/lib/igui/igui.txt:318-326` defines `Work Area` as the client area and
  says iGUI updates its bounds when the user drags the size button.
* `main/lib/igui/igui.txt:337-343` exposes `New Display Width` and `New Display
  Height`; changes become effective through `=> Resize Display`.
* `main/lib/igui/igui.txt:1697-1730` implements `Resize Display`, prepares the
  hidden `Backdrop Layer`, updates bounds, and invokes the application’s
  `Work Area Manager`.
* `main/lib/igui/igui.txt:740` allocates `Backdrop Layer`; the stock client
  example writes to it in `examples/iGUIcli.txt:120-128` and then lets iGUI
  present it.
* `main/lib/igui/igui.txt:506-524` defines `Work Area Manager` and `Control
  Loop` callback pointers. The internal loop calls the client control hook on
  every frame.
* `main/lib/igui/igui.txt:293-315` documents `Control Loop Idle Slice`,
  `Always Clear Work Area`, and the `Client Owns Mouse Pointer` / `Client Owns
  Text Cursor` ownership flags. A game client should normally set
  `Always Clear Work Area = NO` and repaint the complete backdrop itself.
* `main/lib/igui/igui.txt:543-550` and `2000-2016` expose the folded-window
  state (`Fold Is Active`) and the `Now Fold`/`Now Unfold` path. Folded windows
  show only the caption and must not be treated as a normal render viewport.
* `main/lib/igui/igui.txt:2018-2080` supplies maximize, fullscreen, and return to
  cooperative/windowed mode. Fullscreen changes are presentation state, not a
  license to alter the graded source framebuffer.
* `examples/icon_editor/iconed.txt:142-145`, `1459-1461`, and `1654-1656`
  demonstrate changing dimensions through `New Display Width/Height` and
  calling `Resize Display`; its work-area manager is at `1739` onward.
* `main/lib/igui/vcons.txt:186-189` records that a resize changes the work-area
  geometry and that ordinary content should not assume stable bounds during
  the resize operation.

There is no discovered runtime stretch primitive and no native `WM_SIZE`
callback exposed by the Linoleum runtime. The port must therefore own the
software scaler and react through iGUI's documented work-area/display state and
callbacks. Do not add a platform-specific window procedure to the fidelity
path.

## Required refactor boundaries

The current game loop must be split into a simulation/render tick and an iGUI
client shell. The shell owns `Initialize Integrated GUI`, `Enter Integrated
GUI`, the work-area manager, and the control loop. The game owns the 320×200
page and never draws directly using `[Display Width]` as its stride.

Input ownership must be explicit. In the iGUI control callback, only consume
keyboard/mouse state when `Client Owns Text Cursor` / `Client Owns Mouse Pointer`
allow it; menus, buttons, and resize controls belong to iGUI. Translate client
coordinates back through the aspect-fit rectangle before using them for game
input. Pointer events in letterbox bars are outside the game viewport.

During a resize, allow iGUI to finish updating `Work Area` and bounds before
repainting. A safe policy is to pause presentation (and, if necessary, the
simulation tick) while dimensions are unstable, then recompute the fit and
resume on the next complete callback. Never partially scale or grade a frame
whose destination geometry changed halfway through a copy. Folded/iconified
windows may skip rendering while preserving a responsive control loop.

## Implementation phases

1. Add a minimal iGUI shell around the already-authentic game, fixed at a
   320×200 logical page. Prove that the existing loop still runs at its normal
   cadence and that quit/fold/unfold controls work.
2. Implement a pure software nearest-neighbour scaler: source 320×200,
   destination rectangle derived from the current `Work Area`, centered with
   bars and preserving 8:5. Keep the scaler independent of iGUI and test it
   with synthetic pages.
3. Connect the scaler to the work-area manager and `Backdrop Layer`. Repaint
   the backdrop completely, then use iGUI's refresh path. Add explicit
   resize/fold pause and callback-state handling.
4. Add window-size controls/presets through `New Display Width/Height` and
   `Resize Display`; retain iGUI's minimum/maximum/physical-size limits. Add
   fullscreen/maximize integration only after windowed behavior is sound.
5. Add the optional 4:3 presentation policy and coordinate mapping. It remains
   an ungraded display variant until an independent presentation oracle exists.

## Verification gates

The scaler needs three-way tests where practical: an independent Python model,
a small C/reference implementation, and the port. Cover at least: exact
320×200 (1×), integer 2×/3×/4×, non-integer available windows, too-wide and
too-tall windows, one-pixel boundary cases, bars, and source/destination
coordinate inversion. Deliberately perturb each implementation so every gate
can be shown to fail.

GUI/manual gates should verify: initial 8:5 window; drag-resize in both axes;
no distortion; centered bars; input remains correct after resize; menu and
resize controls retain ownership; fold/unfold; maximize; fullscreen and
return; clean quit; and no stale pixels at the edges. Run a long resize/fly/
fold soak at the normal frame cadence and watch CPU, memory, and responsiveness.

The authentic 320×200 framebuffer, simulation state, renderer traces, and
existing Wave 10 D/R/J grades remain the authority. GUI composition, host
window dimensions, scaling pixels, bars, DPI behavior, and 4:3 presentation
are **NOT-GRADED** until separately specified and independently checked.
Platform-specific window-manager behaviour is also NOT-GRADED; record it as
an integration limitation rather than weakening the game oracle.

## Non-goals and cautions

This wave does not revise vehicle geometry, rasterisation, camera math, or the
game's 30-fps timing. It does not modify anything under `main/`; the stock iGUI
library is consumed as supplied. It also does not assume a host-native resize
event or a GPU texture/stretch API. The first implementation should be
windowed and software-only, with later fullscreen and 4:3 modes explicitly
marked as presentation features.
