# Changelog

## 3.3.0 - 2026-10-30
- New Learn mode (`references/learn.md`): walks the project's core design areas, describes the current design, and records the user's relevance (weak, medium, strong) in the project's `frontend-design-intent.md`.
- Guard and Explore read the intent file: strong areas are announced and confirmed before they change, medium is case by case, weak needs no ask; Guard amends update the entry.
- Description gains the Learn trigger.

Why: Guard asked about every deviation equally, with no way to tell a design the user cares about from one that landed by accident.

## 3.2.0 - 2026-10-30
- Description tail is a concrete Explore trigger (ideas, alternatives, a new theme, a revamp).
- Guard states the prompt order: screenshot permission, then conform/amend per deviation.
- Interaction: pixel sizing is a positive rule (real pixels or size variables, no `zoom` or scale transforms).
- Gaps section: cap wording "N more omitted (minor)".
- Pruned default-following lines (captions, right-aligned numbers, borders/badges sentence, bare-element clause in Reuse); removed the Reply checklist and the project name from `references/explore.md`.
- Two near-miss false cases in `references/trigger-cases.md`; older entries collapsed.

Why: review of 3.1.0 found vague wording, an unordered pair of user prompts, a project name in a generic file, and lines the model follows anyway.

## 3.1.0 - 2026-10-30
- Description rewritten with a trigger clause, no project names.
- New mode selector: Guard (default, deviations listed and conformed or amended) and Explore (`references/explore.md`).
- Completion criteria for Build, Check and Look at it; screenshots optional (styles read instead, look reported unchecked).
- Project file step falls back to `docs/DESIGN.md`, then the nearest screen's styles, then asks.
- Pruned the intro sentence; positive wording for captions, colour tokens and pixel sizes.
- New closing "Gaps in frontend-design" section; `references/trigger-cases.md` added.

Why: UI changes drifted from the rules without anyone noticing, and ideas beyond the rules had no safe path; Guard makes each deviation an explicit decision and Explore keeps proposals separate from edits.

## 3.0.0 - 2026-10-30
- SKILL.md is generic (apps and sites); the Kedalion rules moved to `projects/kedalion/frontend-design.md`.
- Revamp and icon references, icon packs (`assets/`) and icon scripts moved to `projects/kedalion/frontend-design/` (Kedalion only).
- New step: read the project's `frontend-design.md` (next to its index) when it exists.

Why: the skill must serve Kedalion and minha-bancada; project design systems belong with the project's knowledge, not in the shared skill.

## 1.x–2.0.0 - 2026-10
- Kedalion-specific button, `docs/DESIGN.md` and path rules; all moved to the project file in 3.0.0.
