NOCTIS IV -- L.in.oleum port
============================

Windows: keep every bundled file together and double-click
"Play Noctis IV.cmd". Do not launch Noctis-IV.exe directly from another
program: the launcher is what keeps all relative game files in this folder.

macOS: drag "Noctis IV.app" to Applications and open it normally. Separate
packages target Intel/x86_64 Macs and Apple-Silicon/arm64 Macs; Apple Silicon can
also run the x86_64 package through Rosetta 2. Both are ad-hoc signed rather than
notarized. If macOS 15 or newer blocks the first launch, open System Settings,
choose Privacy & Security, then choose Open Anyway for Noctis IV and confirm. On
older macOS versions, Control-clicking the app and choosing Open may provide the
equivalent override. Do not launch Noctis-IV.game inside the bundle directly.

The game creates CURRENT.LIN and may append names to STARMAP.BIN and player
notes to GUIDE.BIN. Windows stores these beside the launcher; macOS stores them
under ~/Library/Application Support/Noctis IV. Diagnostic output is kept in the
same data folder rather than whichever folder happened to start the game. A
verified save also refreshes CURRENT.BAK; if CURRENT.LIN is present but damaged,
the game restores that last-known-good copy and says so onscreen. Back up
CURRENT.LIN, STARMAP.BIN, and GUIDE.BIN to preserve a journey and its Galactic
Guide notes. A deliberately missing checkpoint starts a clean flight; enter NEW
in GOES to deliberately restart.

Essential controls
------------------
F10               native GAME menu (Up/Down and Enter)
W/A/S/D           walk or strafe
Left mouse hold   surface: walk forward using the original mouse control
Ctrl + W/A/S/D    stalk slowly near surface birds
0-9               select/cancel automatic surface cruise speed; 0 stops
J / hold Space    jump / use the surface jetpack; C cancels thrust
L while airborne add the original downward impulse
Right mouse drag  look around inside the game view
Arrow keys        look in all four directions
E                 start the roof lift from inside the Stardrifter;
                  walk into the roof cupola opening to return automatically
First wall panel   Enter focuses physical GOES; Enter submits a command
Third wall panel   Enter approaches; at STANDBY, Enter selects a landing site
G                  open the large GOES view anywhere in the ship
NEXT              target and fly to a nearby generated star
STAR X Y Z        target exact galactic coordinates
WHERE name        identify a charted star or a planet's parent system
PAR name[:range]  recover source coordinates; use _ for spaces in names
ST name[:range]   target a named star or reached-system planet
SL [range]        list all charted stars or scan the nearby procedural cube
DL name[:range]   list a charted system's planet/moon dependency tree
CAT name[:X..Y]   read ranged records from the original Galactic Guide
PRI name[:X..Y]   export ranged Guide text to GUIDE-PRINT.TXT
PRIF name[:X..Y]  export ranged Guide text to historical GDOUTPUT.TXT
CAST name:notes    append a persistent Galactic Guide note (76 characters max)
REP name:X:notes   correct local guide record X; original records are protected
DELE name[:X..Y]   remove ranged local guide records; original records are protected
REPAIR             mark later duplicate starmap and Guide records as Removed:
CLEAN              compact removed local starmap and Galactic Guide records
OUTBOX             export local labels/notes to OUTBOX.ZIP
INBOX              import a received packet named INBOX.ZIP
X text             send text through the Xnice X.TXT/XBUFF.TXT file queue
X                  promote the next queued Xnice message when X.TXT is absent
IMPORTGD           not required: this build already uses native GUIDE.BIN
CLR               clear the retained GOES output tree
L                 ship: approach/site fallback; surface: downward impulse
Site selector     arrows choose longitude/latitude; L/Enter descends; C cancels
[ and ]           select every generated planet or moon
R                 ship: onboard devices/back; surface: capsule-return fallback
Walk out and back automatic capsule return across the 1,600-unit boundary
6 / 7 / 8 / 9     select a displayed onboard page or command
Navigation page   amplifier / finder / tracking mode / anti-radiation
Misc page         internal light / remote / local / environment data
Cartography page  label star/body / browse nearby targets / manual target
Target browser    6 previous / 7 next / 8 select / 9 cartography
Emergency page    reset systems / rescue / lithium collector / clear status
C / H             lithium collection / depleted-ship rescue
GOES: HELP         list the live resident GOES modules and commands
F4 / F5           FPS display / presentation cadence toggle
                  (desktop defaults to smooth 60 Hz; alternate is authentic 18.2 Hz)
+ / -             brighten / dim the source HUD and visor frame
F6 / F7           save / load checkpoint
F8                soundtrack on/off
F3                original moviemaker panel
  + / -           capture every 1 to 999 source gameplay frames
  Ctrl + / -      select movie deck 001 to 999
  F               tracking-line or black-flash capture treatment
  Enter / P       start or stop recording / pause or resume
                  raw frames are saved under MOVIES\DDD\########.BMP
M or *            save the next numbered 320x200 BMP in GALLERY
B or Delete       save a raw 320x200 BMP without port display overlays;
                  Delete is the original surface alias
N or /            surface: save a three-panel 916x200 panorama
V or .            surface: save the raw panorama variant
I                 cycle remote, local, and environment data sheets
F1                original Noctis IV+ About page
? or F9           complete current-port control card
Esc               save and quit

Presentation remains the authentic 320x200 renderer, nearest-neighbour scaled
inside a resizable 8:5 iGUI host. Gameplay simulation remains 18.206 Hz in both
presentation modes. Landed HUD telemetry reports fractional gravity,
temperature, atmospheric pressure, and movement-sensitive pulse.

NIV+ surface content is live rather than decorative documentation: generated
habitable worlds can contain full branch-stack trees, mammals/hoppers and
landing or flying birds; birds can be stalked and captured. The three historical
systems contain all six original ruin styles, and Suricrasia at LQ 018:060
contains the original 25-by-25-cell Cube. The capsule shell is transparent; its
structural line modes and skyward beacon follow the original source.

Credits and distribution
------------------------
Noctis IV: Alessandro Ghignola, Copyright 1996-2002.
L.in.oleum: Alessandro Ghignola, Copyright 2001-2004.
Manual soundtrack: Ryan J. Bury. The original silent experience remains
available with F8. This port is distributed under the original WTOF Public
License with the author's authorisation; see WPL.htm for the full terms and
credits. Redistribution must remain free and comply with that licence.
