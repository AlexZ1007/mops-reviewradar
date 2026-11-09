---
name: ReviewRadar
description: Product-review projects for product teams, set as a clean proof sheet marked in editor's red pencil.
colors:
  pencil: "#b0122b"
  pencil-wash: "#f8e4e7"
  ink: "#1a1a1a"
  graphite: "#5f5b57"
  rule: "#e7e4e0"
  tint: "#f6f5f3"
  sheet: "#ffffff"
typography:
  display:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "2.6rem"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "2.5rem"
    fontWeight: 600
    letterSpacing: "-0.015em"
  section:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "1.2rem"
    fontWeight: 600
  title:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "1.15rem"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Hanken Grotesk, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  body-sub:
    fontFamily: "Hanken Grotesk, sans-serif"
    fontSize: "0.92rem"
    fontWeight: 400
    lineHeight: 1.45
  meta:
    fontFamily: "Hanken Grotesk, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 400
  label:
    fontFamily: "Hanken Grotesk, sans-serif"
    fontSize: "0.9rem"
    fontWeight: 500
  wordmark:
    fontFamily: "Hanken Grotesk, sans-serif"
    fontSize: "1.05rem"
    fontWeight: 700
    letterSpacing: "-0.01em"
rounded:
  none: "0px"
  control: "6px"
  full: "50%"
spacing:
  row-y: "14px"
  margin: "30px"
  page-x: "2rem"
  page-x-mobile: "1rem"
  bar-gap: "2rem"
  bar-after: "2.5rem"
  section-before: "2.25rem"
  page-bottom: "5rem"
  column: "1040px"
components:
  button-primary:
    backgroundColor: "{colors.pencil}"
    textColor: "{colors.sheet}"
    rounded: "{rounded.control}"
  button-secondary:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
  button-secondary-hover:
    textColor: "{colors.pencil}"
  button-tertiary:
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
  project-link:
    textColor: "{colors.ink}"
    typography: "{typography.title}"
    padding: "0"
  project-link-hover:
    textColor: "{colors.pencil}"
  input:
    backgroundColor: "{colors.tint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
  top-bar:
    backgroundColor: "{colors.sheet}"
    height: "60px"
  nav-tab:
    textColor: "{colors.graphite}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "18px 2px 17px"
  nav-tab-active:
    textColor: "{colors.ink}"
  row:
    padding: "14px 0 14px 30px"
  avatar:
    backgroundColor: "{colors.tint}"
    textColor: "{colors.ink}"
    rounded: "{rounded.full}"
    size: "32px"
  avatar-me:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet}"
---

# Design System: ReviewRadar

## Overview

**Creative North Star: "The Editor's Red Pencil"**

The workspace is a clean proof sheet. Everything is set in ink on white, separated by hairline rules the way a galley proof is ruled, and the only colour on the page is the editor's crimson pencil. The pencil marks two things: what needs your decision, and where you are. It underlines the current tab, circles the row waiting for your answer, fills the one main action on a page, and carries the caret and focus ring. Nothing is crimson for decoration.

Density is calm and list-shaped: one 1040px column, a serif title with one line of facts beneath it, the page's main action at the right, then ruled rows. Every row keeps a 30px left margin, and that margin is where the pencil ring is drawn. The system refuses the sidebar-plus-card-grid dashboard: navigation lives in a white top bar, content lives in rows, not cards, and panels carry no shadow.

Type does the hierarchy work. Source Serif 4 semibold is the editor's hand for page titles, section heads and project names; Hanken Grotesk carries every piece of interface. Motion is a single gesture: the ring draws itself in once when the page loads, and stays static under reduced motion.

**Key Characteristics:**
- White sheet, ink text, graphite secondary text, hairline rules; crimson used only as a pencil mark.
- Serif for names and titles, grotesk for UI.
- Hairline-ruled rows with a reserved 30px left margin; a hand-drawn crimson ring in that margin marks rows that need a decision or are unread.
- White sticky top bar; the current tab is underlined in crimson.
- Flat panels; creation and invitation happen in popovers anchored to the page's main action; the project page splits into tabs.
- Gently rounded controls (6px); Material Symbols icons.

## Colors

A near-monochrome proof sheet with one saturated crimson that behaves like a pencil, not a brand fill.

### Primary
- **Editor's Crimson** (pencil): the active-tab underline, the decision ring, primary buttons (New project, Invite people, Accept, Create, Send, Save), link colour, project-name hover, the text caret and the 2px focus outline. Also flags a state that needs attention in running text (Archived, Expired).
- **Pencil Wash** (pencil-wash): text selection only; ink stays the text colour on it.

### Neutral
- **Proof Ink** (ink): all primary text, titles, project names, owner role, the signed-in user's avatar fill.
- **Graphite** (graphite): secondary text: meta lines, row sub-lines, captions, inactive nav tabs, non-owner roles.
- **Hairline** (rule): every row divider, the top-bar underline, the tab track, widget borders, the danger-zone top rule.
- **Margin Tint** (tint): row hover wash, other members' avatars, input and secondary widget fill.
- **Sheet** (sheet): the page and the top bar.

### Named Rules
**The Pencil Rule.** Crimson marks only what needs a decision or where you are. If a crimson element answers neither "act here" nor "you are here", it is decoration and comes out.

**The One Hue Rule.** There is no secondary or tertiary accent. Hierarchy comes from ink versus graphite and from serif versus grotesk, never from a second colour.

## Typography

**Display Font:** Source Serif 4 (with Georgia, serif), loaded at weight 600 only
**Body Font:** Hanken Grotesk (with sans-serif), weights 400 / 500 / 600 / 700

**Character:** A bookish semibold serif for the things that have names, paired with a plain, slightly warm grotesk for everything you operate. The serif reads as the editor's annotation; the grotesk as the form being edited.

### Hierarchy
- **Display** (600, 2.6rem, 1.1, -0.02em): the sign-in headline only; 2rem under 640px.
- **Headline** (600, 2.5rem, -0.015em, balanced wrap): the page title (Projects, Inbox, the project's name); 2rem under 640px.
- **Section** (600, 1.2rem): serif section heads inside a page ("Waiting for your answer", "Your projects").
- **Title** (600, 1.15rem, 1.3): project names in rows (as the link), invitation titles, empty-state and danger-zone titles.
- **Body** (400, 15px base, 1.5): row lines and notification text; emphasis is 600-700 ink.
- **Body Sub** (400, 0.92rem, 1.45, max 62ch, clamped to two lines): graphite sub-line under every row title.
- **Meta** (400, 0.95rem): the one line of facts under a page title, graphite with key facts in 600 ink; counts use tabular numerals.
- **Label** (500, 0.9rem-1rem): nav tabs, tab labels, role text; the active nav tab goes to 600 ink.
- **Wordmark** (700, 1.05rem, -0.01em): "ReviewRadar" beside the radar mark.

### Named Rules
**The Named Things Rule.** Serif is reserved for page titles, section heads and project names. Buttons, labels, meta, roles and body copy are always Hanken Grotesk.

**The Tabular Count Rule.** Counts in a page's meta line use tabular numerals.

## Layout

A single centred column, max 1040px wide, with 2rem side padding (1rem under 640px) and 5rem of bottom room. The sticky top bar sits at the top, full-bleed white, at least 60px tall, with 2rem between its items (1rem on mobile) and 2.5rem below it before the page head.

The page head is a two-column split: title plus one meta line at the left, the page's single main action right-aligned and bottom-aligned with it. Below that, content is a vertical stack of ruled rows. Rows pad 14px top and bottom and 30px on the left; that left margin is reserved on every row, marked or not, so marked and unmarked rows align. Row content splits into a wide text column and a right-aligned actions or role column. Section heads sit 2.25rem above their rows. Filters above a list are a segmented control carrying counts.

Under 640px the wordmark collapses to its mark and titles drop to 2rem; the column structure otherwise holds.

## Elevation & Depth

Flat. Panels, rows and the top bar carry no drop shadow; depth is conveyed by hairline rules, the white top bar against the white sheet with a single rule under it, and the tint wash on row hover. Two box-shadows exist in the code and neither is elevation: the top bar paints itself full-bleed with a 100vmax spread of sheet white, and the active nav tab draws its crimson underline as an inset 2px shadow. Floating layers that Streamlit renders natively (popovers, the confirm dialog, toasts) keep their native shadow; that is the only lifted surface in the system.

### Named Rules
**The Ruled Sheet Rule.** Separate content with a 1px hairline, never with a card, fill or shadow. Only genuinely floating layers (popover, dialog, toast) lift off the sheet.

## Shapes

Gently rounded controls (6px) for buttons, inputs, selects and popovers. Rows have no shape of their own: they are open bands between hairlines. Nav tabs are square (0) because their underline is the shape. Avatars are full circles (32px). The one organic form in the system is the pencil ring: a slightly irregular, open hand-drawn loop (2.2 stroke, round cap) whose ends overshoot rather than close.

## Components

### Buttons
Quiet and typographic; only one crimson button per context.
- **Shape:** gently rounded (6px).
- **Primary:** crimson fill, white label, often with a leading Material Symbol (add, person_add, check, send). One per page head or per decision row (Accept, beside a secondary Decline).
- **Secondary:** white fill, hairline border, ink label; Streamlit's native hover turns border and label crimson.
- **Tertiary:** chrome-less text button for low-stakes row actions (Leave, Revoke, mark as read).
- **Focus:** 2px crimson outline, 2px offset, on every focusable element.

### Project Link
Project names are the link: serif title (1.15rem / 600) in ink with all button chrome stripped (no padding, no min height, left aligned). On hover it turns crimson with a 1px underline offset 4px.

### Chips (segmented control)
Streamlit's segmented control filters lists (All / Owned by me / Shared with me; Unread / All) and switches Sign in / Create account. Each option carries its count after the label. Selected state follows the theme's crimson primary.

### Inputs / Fields
- **Style:** native Streamlit fields with widget borders on, hairline border, tint fill, 6px radius; labels always visible above the field and helpful placeholders inside.
- **Focus:** crimson border, crimson caret.
- **Forms:** borderless forms inside popovers, with a full-width primary submit.

### Navigation
- **Top bar:** sticky, full-bleed white strip, minimum 60px, one hairline under it. Wordmark (mark + "ReviewRadar") left, then Projects and Inbox as page-link tabs; the account menu (initials in a popover) pushed right.
- **Tabs:** graphite 500 labels, no fill or radius; hover turns the label ink; the current tab is ink 600 with a 2px crimson underline. Inbox carries its unread count ("Inbox · 3").
- **Project tabs:** Streamlit tabs (Members, Invitations, Settings) with counts in the label, a crimson highlight bar and a hairline track.

### Ruled Row (signature)
A band between hairlines with 14px vertical padding and a 30px left margin. Hover washes the row in tint from the margin edge rightward, leaving the margin itself clear. Title in serif or bold ink, a graphite two-line sub-line, and a right-aligned column for role or actions.

### Pencil Ring (signature)
An 18px hand-drawn crimson ring placed in the row's left margin (2px from the edge, 18px from the top) on rows that need the visitor: pending invitations and unread notifications. It draws in once on load as a clockwise sweep starting where the stroke starts (0.6s, `cubic-bezier(.16, 1, .3, 1)`, 0.1s delay) and is static under reduced motion. Rows needing a decision are also sorted first.

### Popover Actions
Create and invite happen in a popover anchored to the page's primary button, holding a borderless form with a full-width primary submit. Per-member management uses a tertiary more_horiz popover. Irreversible leave goes through a confirm dialog; archive sits below a hairline danger rule behind a confirmation checkbox.

### Avatar
32px circle of initials (600, 0.8rem): tint with ink for others, ink with white for the signed-in user.

### Empty State
Serif title plus graphite sub-line, indented to the same 30px margin, 3rem above and 2rem below, closed by a hairline.

## Do's and Don'ts

### Do:
- **Do** reserve the 30px left margin on every row, marked or not, so rows align and the ring has a home.
- **Do** put the pencil ring only on rows that need the visitor's decision or are unread, and sort those rows first.
- **Do** set page titles, section heads and project names in Source Serif 4 600; set everything else in Hanken Grotesk.
- **Do** keep one primary crimson action per page head or decision, with secondary or tertiary buttons beside it.
- **Do** use Material Symbols for every icon.
- **Do** carry counts inside labels (tabs, filters, Inbox) rather than as separate badges or stat tiles.
- **Do** keep the ring's draw-in a single, one-time gesture and static under reduced motion.

### Don't:
- **Don't** use crimson for decoration, backgrounds, or a second meaning beyond "act here" or "you are here".
- **Don't** wrap rows or page content in cards, filled panels or drop shadows; separate with hairlines.
- **Don't** add a sidebar or a card-grid dashboard; navigation lives in the top bar.
- **Don't** introduce a second accent hue.
- **Don't** set buttons, labels or body copy in the serif.
