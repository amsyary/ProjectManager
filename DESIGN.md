---
name: Project Manager
description: A Windows quick launcher where every project is a tool drawer cut from two-layer Kaizen foam.
colors:
  cabinet: "#16181B"
  rail: "#1C1E22"
  foam: "#26292D"
  foam-hi: "#2D3035"
  cut: "#131518"
  cut-hi: "#1C1F23"
  wall-dark: "#08090A"
  wall-light: "#383C42"
  edge: "#33373D"
  shadow: "#000000"
  ink: "#ECE8E0"
  ink-dim: "#A6A49D"
  ink-faint: "#8E8D88"
  yellow: "#F2B705"
  yellow-hi: "#FFC727"
  yellow-wall: "#A97F00"
  on-yellow: "#17150F"
  red: "#E5534B"
  on-red: "#FFFFFF"
  tape: "#111214"
  tape-ink: "#F3F1EC"
  light-cabinet: "#C6C8C9"
  light-rail: "#D2D4D5"
  light-foam: "#E8E9EA"
  light-foam-hi: "#F2F3F4"
  light-cut: "#CFD1D2"
  light-cut-hi: "#C4C6C8"
  light-wall-dark: "#989B9E"
  light-wall-light: "#FAFBFB"
  light-edge: "#BDC0C2"
  light-shadow: "#4A4E52"
  light-ink: "#1B1C1E"
  light-ink-dim: "#4F5054"
  light-ink-faint: "#55565A"
  light-yellow-hi: "#FFC52E"
  light-yellow-wall: "#B58700"
  light-red: "#C93B33"
  light-tape: "#151618"
typography:
  title:
    fontFamily: "Bahnschrift SemiBold, Bahnschrift, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 600
  body:
    fontFamily: "Bahnschrift, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
  meta:
    fontFamily: "Bahnschrift, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 400
  label-tool:
    fontFamily: "Bahnschrift SemiBold, Bahnschrift, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    letterSpacing: "0.6px"
  label-caps:
    fontFamily: "Bahnschrift, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    letterSpacing: "1px"
  tape:
    fontFamily: "Bahnschrift SemiBold Condensed, Bahnschrift, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    letterSpacing: "0.09em"
  mono:
    fontFamily: "Cascadia Mono, Consolas, Courier New, monospace"
    fontSize: "12px"
    fontWeight: 400
  mono-field:
    fontFamily: "Cascadia Mono, Consolas, Courier New, monospace"
    fontSize: "13px"
    fontWeight: 400
rounded:
  tape: "3px"
  checkbox: "4px"
  list-item: "5px"
  menu-item: "6px"
  slot: "7px"
  popup: "8px"
  drawer-front: "9px"
  menu: "10px"
  slab: "11px"
  panel: "12px"
spacing:
  tool-gap: "4px"
  slab-gap: "6px"
  control-gap: "8px"
  field-row: "10px"
  section: "14px"
  drawer-inset: "18px"
  window-inset: "20px"
components:
  tool-slot:
    backgroundColor: "{colors.cut}"
    textColor: "{colors.ink}"
    typography: "{typography.label-tool}"
    rounded: "{rounded.slot}"
    padding: "0 12px"
    height: "34px"
  tool-slot-hover:
    backgroundColor: "{colors.cut-hi}"
    textColor: "{colors.ink}"
  tool-slot-compact:
    backgroundColor: "{colors.cut}"
    textColor: "{colors.ink}"
    typography: "{typography.label-tool}"
    rounded: "{rounded.slot}"
    padding: "0 10px"
    height: "30px"
  tool-slot-primary:
    backgroundColor: "{colors.yellow}"
    textColor: "{colors.on-yellow}"
    typography: "{typography.label-tool}"
    rounded: "{rounded.slot}"
    padding: "0 12px"
    height: "34px"
  tool-slot-primary-hover:
    backgroundColor: "{colors.yellow-hi}"
    textColor: "{colors.on-yellow}"
  tool-slot-checked:
    backgroundColor: "{colors.yellow}"
    textColor: "{colors.on-yellow}"
  tool-slot-danger-hover:
    backgroundColor: "{colors.red}"
    textColor: "{colors.on-red}"
  tool-slot-quiet:
    textColor: "{colors.ink-dim}"
    rounded: "{rounded.slot}"
    height: "34px"
  tool-slot-out:
    backgroundColor: "{colors.yellow}"
    textColor: "{colors.on-yellow}"
    typography: "{typography.mono}"
    rounded: "{rounded.slot}"
    height: "34px"
  tool-slot-disabled:
    backgroundColor: "{colors.cut}"
    textColor: "{colors.ink-faint}"
  input:
    backgroundColor: "{colors.cut}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.slot}"
    padding: "6px 10px"
  input-hover:
    backgroundColor: "{colors.cut-hi}"
  input-mono:
    backgroundColor: "{colors.cut}"
    textColor: "{colors.ink}"
    typography: "{typography.mono-field}"
    rounded: "{rounded.slot}"
    padding: "6px 10px"
  foam-panel:
    backgroundColor: "{colors.foam}"
    textColor: "{colors.ink}"
    rounded: "{rounded.panel}"
    padding: "16px 16px 20px 18px"
  folder-slab:
    backgroundColor: "{colors.foam}"
    textColor: "{colors.ink}"
    rounded: "{rounded.slab}"
    padding: "12px 12px 16px 14px"
  drawer-front:
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.drawer-front}"
    height: "64px"
  drawer-front-hover:
    backgroundColor: "{colors.foam}"
  drawer-front-open:
    backgroundColor: "{colors.foam-hi}"
    typography: "{typography.title}"
  dymo-tape:
    backgroundColor: "{colors.tape}"
    textColor: "{colors.tape-ink}"
    typography: "{typography.tape}"
    rounded: "{rounded.tape}"
    padding: "0 9px 0 11px"
    height: "28px"
  icon-well:
    backgroundColor: "{colors.cut}"
    size: "44px"
  menu:
    backgroundColor: "{colors.foam}"
    textColor: "{colors.ink}"
    rounded: "{rounded.menu}"
    padding: "6px"
  menu-item-selected:
    backgroundColor: "{colors.yellow}"
    textColor: "{colors.on-yellow}"
    rounded: "{rounded.menu-item}"
    padding: "7px 28px 7px 12px"
  tooltip:
    backgroundColor: "{colors.tape}"
    textColor: "{colors.tape-ink}"
    typography: "{typography.meta}"
    rounded: "{rounded.list-item}"
    padding: "5px 8px"
---

# Design System: Project Manager

## Overview

**Creative North Star: "The Kaizen Shadow Board"**

Project Manager is a tool cabinet. Each project is a drawer; each folder in it is a slab of foam; every action a folder can perform is a tool sitting in its own cut-out. The foam has two layers: a matte top layer (charcoal in dark, pale grey in light) and a flat chrome-yellow under-layer that only shows where something has been cut away. That one physical idea carries the whole system: controls are recessed into the foam rather than raised off it, yellow appears only where the top layer is gone (launch actions, focus, checked states, running tools), and a running Flutter app reads as an empty slot with its tool lifted out.

The density is that of a launcher opened many times a day for a few seconds: a rail of drawer fronts on the left, the open drawer filling the rest, a thin top strip for the editor, terminal, scrcpy and snippets. Names go on Dymo label tape, every label is set in DIN (Bahnschrift), and Cascadia Mono is kept for data: paths, commands, logs and the running clock. The system refuses the VS Code clone of grey panels with blue buttons; there is no blue anywhere.

Both themes are the same object under different light. Dark is the default; light swaps the foam to pale grey and keeps the yellow, the tape and the cut-out geometry identical.

**Key Characteristics:**
- Two depths only: raised foam slabs and recessed cut-outs.
- One accent (chrome yellow) used as an under-layer, never as paint.
- Two text sizes inside a drawer (14 and 12); rank comes from weight, case and reversal.
- Authored single-stroke icon set on a 24px grid; no glyph or emoji icons.
- Tools keep their width through every state, so rows never reflow.

## Colors

A near-monochrome foam palette with one hot under-layer and one red reserved for removal and failure.

### Primary
- **Chrome Yellow** (`yellow`): the under-layer. Floor of primary tools (Open all, Run, Save project), checked toggles and mode buttons, pressed tools, menu and list selection, text selection, focus rings (2px around tools, 1px on fields), the pull handle of the open drawer, the running dot on a drawer front, the busy/running status lamp and the build scan bar. Its hover lift is **Bright Yellow** (`yellow-hi`), and its cut wall is **Ochre Wall** (`yellow-wall`), used for the upper wall of a yellow cut-out and the dashed outline of a lifted tool.
- **Yellow Ink** (`on-yellow`): the only ink allowed on a yellow floor.

### Secondary
- **Signal Red** (`red`): danger and failure only. The hover floor of delete and Stop tools (which sit neutral at rest), error text for missing paths, the error lamp, and error lines in the Flutter log. Its ink is `on-red`.

### Neutral
- **Cabinet** (`cabinet`): window ground behind everything.
- **Rail** (`rail`): the top strip and the drawer rail, one step lighter than the cabinet.
- **Foam** (`foam`) and **Pulled Foam** (`foam-hi`): the top layer of slabs, menus and drawer fronts; `foam-hi` marks the open drawer front.
- **Cut Floor** (`cut`) and **Lit Floor** (`cut-hi`): the floor of every recess: tools, inputs, icon wells, the scan-bar track. `cut-hi` is the hover floor.
- **Shadowed Wall** (`wall-dark`) and **Lit Lip** (`wall-light`): the upper wall and lower lip that make a recess read as cut in.
- **Hairline Edge** (`edge`): the 1px outline of foam, menu borders, separators, scrollbar handles.
- **Bone Ink** (`ink`), **Dust Ink** (`ink-dim`), **Faint Ink** (`ink-faint`): primary text; metadata, caps labels, paths; disabled text, placeholders and icon fallbacks. In light, faint ink sits almost on dim ink so disabled text keeps readable contrast on pale foam.
- **Label Tape** (`tape`) and **Tape Ink** (`tape-ink`): Dymo tape bodies and tooltips, near-black in both themes.

Light theme values carry the `light-` prefix in the frontmatter; `yellow`, `on-yellow`, `on-red` and `tape-ink` are shared by both themes.

### Named Rules
**The Under-Layer Rule.** Yellow is never painted on top of the foam; it is what shows where the foam is cut away. It is reserved for launch/primary, focus, checked/selected/open and running. It is never a text color on foam.

**The One Launch Per Slab Rule.** A slab, dialog or window has at most one primary (yellow) tool: Open all in the drawer header, Run in the Flutter window, Save in a dialog. Every other tool is a normal cut-out.

**The Red Means Remove Rule.** Red marks deletion, stopping and failure. Danger tools rest as ordinary cut-outs and only show their red floor on hover.

## Typography

**Label Font:** Bahnschrift (DIN), with Bahnschrift SemiBold for weight and Bahnschrift SemiBold Condensed for tape
**Mono Font:** Cascadia Mono (with Consolas, Courier New)

**Character:** Engineering signage. DIN gives every label the voice of a stamped part number; condensed capitals on tape name the drawer; mono marks anything that is literal data the user could paste.

### Hierarchy
- **Tape** (SemiBold Condensed, 14px, 0.09em tracking, uppercase, reversed out of black tape): the project name, in the drawer header and the Flutter run window header. Nowhere else.
- **Title** (SemiBold, 14px): folder names in a slab, the open drawer front's name, the window mark, status words ("Stopped"), empty-state headings.
- **Body** (Regular, 14px): unselected drawer-front names, input text, dialog prose.
- **Label / Tool** (SemiBold, 12px, 0.6px tracking, uppercase): every tool label ("OPEN ALL", "TERMINAL").
- **Label / Caps** (Regular, 12px, 1px tracking, uppercase, Dust Ink): field labels and folder types ("CONFIGURATION", "FLUTTER", "EDITOR").
- **Meta** (Regular, 12px, Dust Ink): counts, hints and shortcut legends ("3 folders · opened 2×").
- **Mono** (12px, Dust Ink): paths in slabs and headers; the running tool's label ("Building 0:42") in mixed case on yellow.
- **Mono Field** (13px): text fields that hold paths, targets or args, and the Flutter log.

### Named Rules
**The Two Sizes Rule.** A drawer uses exactly two text sizes, 14 and 12. Rank is expressed by weight (SemiBold vs Regular), case (caps vs mixed) and reversal (tape), never by a larger size.

**The Mono Is Data Rule.** Cascadia Mono is only for literal data: paths, commands, arguments, logs, and the running clock on a lifted tool. Never for labels or headings.

**The Caps Are For Tools Rule.** Tool labels are uppercase; a tool that is out (running) switches to mixed-case mono, so state change reads as a change of material, not just color.

## Layout

The main window is a cabinet (default 1200 x 760, minimum 880 x 540) split into three columns by a 1px splitter: the drawer rail (minimum 250px, opens at 300px), the open drawer (takes all stretch), and an optional snippets column (320px; showing it widens the window to 1300px if narrower). A top strip runs across the full width with 16/8/12/8 padding and 8px gaps.

The rail stacks a search field, the drawer fronts (64px rows, most-opened first) and a full-width Add project tool, each with a 12px side gutter. The drawer is a scroll column inset 18px left/right, 16px top, holding a header slab and then one slab per folder, 6px apart.

Spacing steps are fixed and few: 4px between tools in a row, 6px between slabs, 8px between controls, 10px between form rows, 14px between window sections, 18px drawer inset, 20px dialog inset. Slab bottom padding is 4px deeper than the top because the foam's shadow lip occupies the bottom of its rect.

Responsive behavior is measured, not breakpoint-driven. Inside a slab the icon well, info column (minimum 280px) and tool row sit side by side with tools right-aligned; when the slab is narrower than well + info minimum + the tool row's natural width, the tools drop below the info line, left-aligned, and wrap only if they still don't fit. In the top strip, the "Project Manager" title and the EDITOR / TERMINAL caps labels hide below a 1080px window width: labels give way before controls do.

### Named Rules
**The Drop, Don't Squeeze Rule.** When a slab gets narrow, tools move below the info line as a group; they never shrink, truncate their labels, or overlap the path.

**The Reserved Width Rule.** A tool whose label changes with state reserves the width of its widest label up front (Start reserves "Building 0:00", "Stopping 0:00" and "Running" in mono), so rows never reflow when something starts or stops.

## Elevation & Depth

Depth is physical and has exactly two directions. Foam slabs are raised: a matte fill with a fine speckle texture (a 128px noise tile, alpha 16 in dark, 13 in light), a 1px hairline edge, a faint top highlight, and a soft drop built from three stacked offsets (1px, 2px, 4px at very low alpha, halved in light). Everything interactive is cut in: a flat floor, a 6px gradient of shadowed wall along the top inside edge, and a 1px lit lip along the bottom. Menus and combo popups are flat foam sheets with a hairline edge and no OS drop shadow. Dymo tape sits on the foam with a 1.5px drop that gives the tape its thickness.

### Shadow Vocabulary
- **Foam drop**: stacked 1px / 2px / 4px offsets of the slab shape in `shadow` at alpha 34 / 18 / 10 (dark) or half that (light). Raised slabs, the open drawer front, empty-drawer inserts.
- **Cut wall**: a 6px vertical gradient inside the top edge from `wall-dark` (alpha 150 dark, 110 light) to transparent, plus a 1px `wall-light` lip at the bottom. Every tool, input, icon well and checkbox.
- **Tape drop**: the tape shape offset 1.5px down in black at alpha 70. Dymo tape only.

### Named Rules
**The Slab And Cut Rule.** There are two depths: raised foam and recessed cut-outs. Nothing interactive is raised; nothing structural is recessed. Hover lightens a floor or pulls foam forward (`foam-hi`); it never adds a new shadow.

## Shapes

Corners are rounded and nest: each container is a step softer than what it holds. Panels 12px, folder slabs 11px, menus 10px, drawer fronts and rail icon pockets 9px, popups 8px, tool slots and inputs 7px, menu items 6px, list items and tooltips 5px, checkboxes 4px, tape 3px. Icon wells scale their radius with their size (22% of the side, at least 6px). The only outlines that are not hairlines are state outlines: the 2px yellow focus ring, the dashed ochre outline of a lifted tool, and the dashed faint outlines of ghost slots and empty-drawer silhouettes.

Icons are authored silhouettes on a 24px grid with a single 1.8 stroke, round caps and joins, rendered at 16px in the tool's current ink. Only play, stop, bolt and more are filled.

## Components

### Tool Slots (buttons)
The tool in its cut-out: tactile, recessed, and honest about state.
- **Shape:** gently rounded recess (7px), 34px tall (30px compact), 12px side padding (10px compact), icon 16px with a 7px gap to the label, optional 12px chevron for menus.
- **Normal:** `cut` floor, `ink` label in uppercase SemiBold 12px.
- **Hover:** the floor eases to `cut-hi` over 140ms (OutCubic) and the contents lift 1px; pressed drops them 0.5px and turns the floor yellow.
- **Focus:** a 2px yellow ring just outside the slot (keyboard focus only; tools take Tab focus, Enter activates).
- **Primary:** yellow floor with `yellow-wall` upper wall and `on-yellow` ink; hover brightens to `yellow-hi`. Used once per slab or dialog.
- **Checked / active:** same yellow floor as primary (mode buttons, service-extension toggles, Snippets when open).
- **Danger:** neutral at rest, red floor with white ink on hover (delete, Stop).
- **Quiet:** no visible slot until hovered; ink eases from `ink-dim` to `ink`. Icon-only secondary tools (edit, more, theme, clear log).
- **Out (running):** the tool has been lifted out: a yellow under-layer floor, a dashed `yellow-wall` outline of the missing tool inset 3.5px, and the label in mixed-case Cascadia Mono 12px ("Building 0:42", "Running"). Used by Start while Flutter runs and by scrcpy while mirroring.
- **Disabled:** `cut` floor with faint ink. **Ghost** variant (service-extension toggles before the app runs): an empty dashed cut-out with no floor.
- "Add project" in the rail is a normal slot stretched to the rail width, not a primary.

### Inputs / Fields
- **Style:** cut-outs: `cut` floor, `wall-dark` top border, `wall-light` bottom border, 7px radius, 6px 10px padding. Text areas pad 8px.
- **Hover:** floor goes to `cut-hi`.
- **Focus:** 1px yellow border all round.
- **Mono fields:** paths, targets and args switch to Cascadia Mono 13px.
- **Combo:** same cut-out with a drawn 12px chevron in `ink-dim`; its popup is a foam sheet (8px radius, 4px padding) with 28px items and yellow selection.
- **Checkbox:** a 16px cut-out (4px radius) that fills yellow with an ochre wall when checked.
- **Error / disabled:** missing paths turn red (12px); disabled field text is `ink-faint`.

### Foam Slabs (cards)
- **Corner Style:** 12px for panels and the drawer header, 11px for folder slabs.
- **Background:** `foam`, speckle texture, hairline `edge`, foam drop (see Elevation).
- **Internal Padding:** header 16 top, 16 right, 20 bottom, 18 left; folder slab 12 / 12 / 16 / 14. Slabs never stretch taller than their content.
- **Layout:** icon well, then info (name in Title, caps type + mono path on one meta line), then tools right-aligned. Double-clicking a folder slab opens it like its Open tool.

### Drawer Fronts (navigation)
The rail is a stack of drawer fronts, 64px tall, inset 8px. Each holds a 40px icon pocket, the project name (Body) and a meta line (Meta). Hover shows the foam front without a shadow and a faint `edge` pull handle; the open drawer is pulled 4px out of the rail, painted `foam-hi` with the foam drop, its name turns SemiBold and its 3px pull handle (up to 64px long, under the text) turns yellow. A yellow 9px dot at the right edge means something in that drawer is running. Search drives the rail: typing narrows to the best match, Up/Down step, Enter moves into the drawer.

### Dymo Tape
White condensed capitals reversed out of near-black tape with the same speckle texture, a 3px radius, a faint top highlight and the tape drop. Height is the text size plus 14px; the name elides at the right. Tape names the project and nothing else.

### Icon Well
A square recessed pocket holding a project or type image at 66% of its side; without an image it shows the authored fallback icon (drawer, folder or launch) in `ink-faint`. Sizes in use: 64px (drawer header), 52px (Flutter window), 44px (folder slab), 40px (rail pocket).

### Menus and Tooltips
Menus are frameless foam sheets: 10px radius, 6px padding, hairline edge, 16px icons in `ink-dim`, items 7px 28px 7px 12px with a 6px-radius yellow selection, hairline separators. They open 2px below the tool that called them. Tooltips are tape: near-black body, tape ink, 12px, 5px radius.

### Status: Lamp and Scan Bar
The **status lamp** (12px) is hollow `ink-faint` when idle, breathes yellow (alpha 0.35 to 1 over 700ms, InOutSine) while building or stopping, is solid yellow when running and red on error. The **scan bar** is a 4px `cut` track with a yellow segment (28% of the width) sweeping across every 1400ms while Flutter builds or stops.

### Empty Drawer
An empty foam insert with dashed `ink-faint` silhouettes of tools that are not there yet (4/3 dash), a centered Title heading, a Meta detail line and at most one tool. The "No projects yet" state's Add project is its single primary.

### Motion
Motion is short and mechanical. Tool hover 140ms OutCubic. Opening a drawer fades its content in over 240ms OutCubic while it slides 14px into place from the right; the opacity effect is removed when done so text stays crisp. Looping motion exists only for honest progress (lamp breathing, scan bar).

## Do's and Don'ts

### Do:
- **Do** cut every interactive control into the foam: `cut` floor, shadowed top wall, lit bottom lip, 7px radius.
- **Do** keep yellow for launch/primary, focus, checked/selected/open and running, and put only `on-yellow` ink on it.
- **Do** show a running tool as an empty slot: yellow under-layer, dashed `yellow-wall` outline, mixed-case Cascadia Mono label with the elapsed time.
- **Do** reserve the widest state label on any tool whose label changes, so rows never reflow.
- **Do** keep a drawer to two text sizes (14px and 12px) and rank by weight, case and tape reversal.
- **Do** drop tools below the info line when a slab is narrow instead of shrinking them.
- **Do** draw new icons in the authored set: 24px grid, 1.8 stroke, round caps and joins, rendered in the tool's ink.
- **Do** design both themes at once from the same tokens; light only changes the foam, never the yellow or the geometry.

### Don't:
- **Don't** build grey panels with blue buttons; there is no blue in this system.
- **Don't** use yellow as text color on foam, as decoration, or on more than one primary tool per slab or dialog.
- **Don't** raise interactive controls off the foam or add new shadow styles; depth is slab-and-cut only.
- **Don't** put anything but a project name on Dymo tape.
- **Don't** add a third text size inside a drawer or use size to rank names.
- **Don't** set labels or headings in Cascadia Mono; mono is for paths, commands, logs and the running clock.
- **Don't** use Unicode glyphs, emoji or third-party icon fonts as icons.
- **Don't** show red at rest on a danger tool; red appears on hover or for a real failure.
