---
name: frontend-design
description: Use when building, restyling or reviewing UI: a screen, component, icon, layout or redesign; checks the change against the design rules and loads the project's own frontend-design file when it has one. Also when the user asks for ideas, alternatives, a new theme or a revamp (Explore mode), or to learn or rate the project's current design (Learn mode).
version: 3.3.0
license: Anthropic, from anthropics/claude-code plugins/frontend-design; adapted
---

# Frontend Design

These rules are generic; each project adds its own design system on top.

## Modes

Pick the mode from the request.

- **Guard** (default): any change that touches the UI. Runs the Process; after Build, compare the diff with the rules (generic and project file) and list each deviation as `rule -> what the change does -> why`. A deviation is any new token, size, radius, colour or component not in the rules; ignore single pixels. When the project has an intent file, a deviation in a strong area is announced and confirmed before Build; medium is case by case; weak needs no extra ask. The user is asked in this order: screenshot permission (Process step 4) first, then, for each deviation: conform (fix the code) or amend (the new way is right, change the rule). On amend, write the rule into the project's `frontend-design.md`; change this SKILL.md only after asking the user separately, and bump the version and changelog then. Done when every deviation is fixed or written into a rule; none left silent.
- **Explore**: only when the user asks for ideas, alternatives, a new theme, button placement, a revamp or a different data presentation; never from an ordinary edit. Follow [references/explore.md](references/explore.md). After the pick it hands over to Guard.
- **Learn**: only when the user asks to learn, review or rate the project's current design ("what's our current design", "learn the design", "review design decisions"). Follow [references/learn.md](references/learn.md). It saves each area's relevance (weak, medium, strong) to the project's `frontend-design-intent.md`; Guard and Explore read that file and treat strong areas as needing confirmation before they change.

## Project file

Find the `~/.library/projects/*/index.md` whose `paths` contains the working directory. If that folder has a `frontend-design.md`, read it before planning: it names the project's tokens, components, sizes, checks and modes, and it wins over this file where it is more specific. Also read `frontend-design-intent.md` there when it exists: Guard and Explore apply its relevance levels (see Learn). No such file: use the repo's `docs/DESIGN.md`, else the styles of the nearest existing screen; if neither exists, ask the user.

## Process

1. **Plan**: name the closest existing screen and follow its patterns; list the components and classes reused, the tokens, and an ASCII wireframe of the panes. Done when every new spacing, colour, control size or radius has a reason, or is removed.
2. **Build** with the shared components and styles; screen styles extend the shared ones without cancelling them. Done when the build uses only shared components and tokens, or each exception is listed for Guard.
3. **Check**: run the project's checks (typecheck, lint, raw-element guards) named in its file. Done when every check named in the project file exits 0, or the failing output is reported.
4. **Look at it** in dark and light (when the project has both), at the narrowest and widest layout it supports. Done when alignment, density against neighbours and text contrast are checked. Then name the one thing removed. Take screenshots only with the user's permission in the session; without it, read the styles instead and report the look as unchecked.

## The system

- **Colour**: tokens only (CSS variables). Accent marks selection, active and primary action; status uses fixed tones (ok, warn, error, info, muted). Surfaces and text step through levels.
- **Type**: one UI face and one mono face for code, paths and values.- **Density**: match the neighbours' control heights and radii; radius grows with level (badges < controls < cards < modals). Use the size variables, not literals.
- **Shadows**: only on floating layers (modal, menu, toast); panels sit flat on borders.

## Layout

- Content first: the data (tree, table, editor, log, article) takes the space; chrome is one toolbar line at most.
- Numbered markers only for real sequences.
- Every state is designed: loading, empty (with the next action), error (with retry), and very long content. Truncate with ellipsis and `title`.

## Reuse

Look for an existing component before building one; a pattern two screens need becomes a shared component. Buttons use the project's button component.

## Interaction

- Every action works from the keyboard: visible `:focus-visible`, arrow-key lists, Escape closes.
- Motion answers an action (open, expand, confirm): 120–200ms, opacity or small transforms, inside `prefers-reduced-motion: no-preference`.
- Size controls with real pixel values or the size variables; leave `zoom` and scale transforms out.

## Writing in the UI

- Strings live in the project's i18n files, not inline.
- Name things by what the user manages. A button says what happens ("Save changes"), and the result keeps the name (button "Delete" → toast "Deleted").
- A meta string `A · B · C` is for separate facts only.

## Gaps in frontend-design

At the end of every run, the reply closes with a `Gaps in frontend-design` list (at most 5, ranked by how much a future run gains; when more than 5 qualify, close with "N more omitted (minor)") or `No gaps.` A gap is one of these kinds:

- **wrong finding**
- **check that judged wrongly**
- **missing check**
- **unclear or contradictory rule**
- **step not followable as written**
- **manual work a script could do**

Each entry gives: kind, file and rule, failure seen, proposed edit. Approved gaps are written to the project's `frontend-design.md` (project-specific) or to this SKILL.md (generic, after asking the user).
