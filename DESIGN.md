# Biminent Tool Design Language

Extracted from the reference products: **Apartment Sheets**
(`Bofakta/src/Biminent.ApartmentSheets.Revit`) and **Auto Finishes**
(`aftomat-room.finishes-main`). Every tool in this extension must follow this
spec. `About.pushbutton` (brand window) and `RenameStudio.pushbutton`
(workhorse tool) are the reference implementations.

## Philosophy

1. **One task, one window.** No wizards, no chained dialogs. Everything the
   user needs to decide is visible at once; the window is sized to the task
   (compact ~380-460 wide for focused tools, large only when a data grid earns it).
2. **Preview before commit.** The user always sees what will happen before it
   happens (Auto Finishes: room checklist; Apartment Sheets: data grid;
   Rename Studio: old → new preview). No blind "OK" buttons.
3. **Safe by default, reversible by design.** Sensible defaults pre-filled.
   Destructive options are explicit checkboxes ("Override existing finishes").
   Creation tools get a companion "Remove" action (danger-styled, never primary).
4. **Selection = filter + checklist + counter.** Element selection uses a
   filter textbox, a checkbox list, Check All / Check None small buttons, and
   an "n/total" counter at the right.
5. **Stay open after acting** when chained use is plausible; report results in
   a status line, not a modal interrupt.

## Window anatomy

- **Standard OS chrome** (Title bar, `ResizeMode="NoResize"` or constrained,
  `WindowStartupLocation="CenterScreen"`). Borderless + gradient header is
  reserved for brand windows (About, progress), not work tools.
- Title format: `<Tool Name>` (the ribbon already says Biminent).
- **Keep the standard OS window chrome** (title bar + border). We do NOT go
  borderless/custom-chrome for work tools — the native frame is fine and
  avoids a whole class of drag/resize/owner bugs. `BiminentWindow` tints the
  native title bar brand-navy via the Win11 DWM API (caption + white text);
  pre-Win11 it stays the default grey, no harm.
- **Brand accent strip**: every tool window ends with a 4px full-width
  `Border` along the **bottom edge**, `Background="{DynamicResource HeaderGradientBrush}"`
  (the teal→navy brand gradient), outside the content margin. Not at the top —
  a colored strip between the title bar and content looks like a glitch.
  Section headings use `HeadingSmallStyle` +
  `Foreground="{DynamicResource PrimaryBrush}"`.
- **List-centric tools use a two-column layout**: compact controls in a fixed
  left column (~280px), the element list filling the right column at full
  window height (~820x680, resizable). The list is the hero — it must never
  show fewer than ~15 rows at default size.
- Section titles are plain `HeadingSmallStyle` TextBlocks with `CaptionStyle`
  field labels — **not** `GroupBox`: its header + border chrome wastes too
  much vertical space (learned from Rename Studio v1).
- Content padding 16,12; only stack sections vertically in genuinely compact
  single-column tools.
- **Bottom bar** (always last row):
  - left: the brand block — `<Image x:Name="brand_logo" Height="24" Width="24"/>`
    plus `<TextBlock x:Name="brand_wordmark" Text="BIMINENT" FontSize="13"
    FontWeight="SemiBold" Foreground="{DynamicResource PrimaryBrush}"/>`;
    both auto-wired clickable (→ biminent.com) by `BiminentWindow`;
    every window carries them — then status/result text
  - right: `[Danger action]  [Primary action]` — primary is `IsDefault="True"`
- **Tool settings**: a `&#x2699;` gear `GhostButtonStyle` button in the top-right
  of the relevant section header opens a small `CenterOwner` settings dialog
  (Cancel/Save); persisted via `biminent.config` to
  `%APPDATA%/Biminent/Tools/<tool>.json`. See Rename Studio.
- Inline warnings: `WarningTextStyle`/`ErrorTextStyle` TextBlock under the
  relevant section, `Visibility="Collapsed"` until needed. Never a popup for
  validation.

## Theme usage (lib/resources/theme)

- Reference everything with `{DynamicResource ...}` (theme merges after XAML load).
- Plain `TextBox/ComboBox/CheckBox/RadioButton/ListBox/DataGrid/ProgressBar`
  are themed implicitly — don't set a style unless you need a named variant.
- Buttons must be explicit: `PrimaryButtonStyle` (one per window),
  `AccentButtonStyle` (promotes a Biminent product/action), `SecondaryButtonStyle`,
  `GhostButtonStyle` (close/cancel), `DangerButtonStyle` (destructive),
  `SmallButtonStyle` (Check All / Check None).
- Text: `HeadingSmallStyle` for section intros, `BodyStyle`/`BodySmallStyle`
  body, `SecondaryTextSmallStyle` for hints, `CaptionStyle` footer,
  `LinkStyle` for hyperlinks.
- Colors come only from theme brushes; never hardcode hex in tool XAML
  (exception: the brand header gradient in brand windows).

## Revit API context — CRITICAL (a crash, not an exception)

Revit API calls (FilteredElementCollector, transactions, `Selection.SetElementIds`,
geometry ops) are only valid inside the command's API context. How the window is
shown decides whether that holds:

- **Modal `ShowDialog()`** — the script thread stays inside `Execute`, so API
  calls in button handlers run in-context. **This is the default for any tool
  that touches the Revit API from its handlers** (Rename Studio, Select in
  Scope Box).
- **Modeless `Show()`** — control returns to Revit; any API call from a later
  handler runs OUT of context and **fatally crashes Revit** (no catchable
  exception). Only use `Show()` if every API call goes through an
  `ExternalEvent` handler.

Never mix modeless `Show()` with direct API calls in handlers. (This crashed
Revit once — Select in Scope Box, fixed by switching to `ShowDialog`.)

## Non-negotiable quality checklist

Every window ships only when all of these hold (each was a real defect once):

1. **Owned by Revit.** `BiminentWindow` sets the Revit main window as owner —
   never instantiate a bare WPF `Window`, or alt-tabbing leaves an invisible
   modal that "freezes" Revit.
2. **Every input is labeled.** No anonymous textboxes; a `CaptionStyle` label
   sits above each field ("Search elements", not a bare box).
3. **Disabled buttons explain themselves.** If the primary action is disabled,
   a visible counter/status must say why ("13 checked · 0 will change").
   The user must never have to guess what the tool is waiting for.
4. **Direct manipulation beats rules.** Where a preview shows a result value,
   let the user edit it in place; batch rules and manual edits coexist
   (manual edit pins the row).

## Error reporting (standard across all tools)

When anything fails, every tool behaves the same way: the **full traceback goes
to the pyRevit output** (diagnosable), and a **short one-liner goes to the
status line** (`status_text`) - never a raw stack-trace dialog in the user's
face. `BiminentWindow` provides this; use it, don't hand-roll:

```python
# wrap an action - errors are logged + shown, the window stays alive:
with self.report_errors("Rename"):
    ... do the work ...   # transactions: try/Commit, except/RollBack+raise

# OR inside an except when you want to keep going (e.g. per-item loops):
try:
    ...
except Exception:
    report.log_traceback("Select in Scope Box - " + name)  # logs, returns msg
```

`self.set_status(text)` writes the status line if the window declares
`x:Name="status_text"`. Reference tools: Select in Scope Box (per-item logging
+ outer guard) and Rename Studio (guard + transaction rollback).

## Code rules

- Subclass `biminent.ui.BiminentWindow`; python logic written from scratch
  (no EF-Tools/pyChilizer code — they are GPL; treat them as feature
  references only, looked at in their own extensions, never copied).
- Transactions named `"Biminent · <action>"` so the undo menu reads well.
- Per-element failures are collected and reported in the status line
  ("Renamed 41 · 2 skipped (duplicate name)"), never abort the whole batch.
- Roadmap note: Revit dark-theme detection (`UIThemeManager.CurrentTheme`,
  see Auto Finishes `ThemeManager.cs`) once a dark variant of Colors.xaml exists.
