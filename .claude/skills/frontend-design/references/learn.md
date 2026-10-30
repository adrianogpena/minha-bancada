# Learn mode

Scope: record which parts of the project's current design the user cares about. Writes only the intent file, never code or rules.

Intent file: `frontend-design-intent.md` next to the project's `frontend-design.md`. One entry per area:

`area -> current design -> relevance -> note`

Relevance:
- **weak**: added this way, no opinion. Also the default for any area without an entry.
- **medium**: added this way, the user likes it.
- **strong**: the user chose or changed it to this and really likes it.

Link to the rules in `frontend-design.md` instead of copying tokens or sizes.

## Procedure

1. Read the rules (generic and project file) and the intent file if it exists. List the core areas (header, buttons, panels, navigation, forms, tables, theme, and any the project file names) and skip the areas already rated. Done when the unrated areas are known.
2. Read the styles and components of one area and describe what the project does there, with each variant: "for the header buttons we have A, B, C". Done when every variant found in code is named.
3. Ask the user to rate the area (weak, medium or strong) and for an optional note, per variant when variants differ. One area per question. Done when every variant of the area has an answer.
4. Write the entries into the intent file after each answer, so a stopped session keeps its progress. Then go to the next unrated area. Done when no unrated core area is left or the user stops.

## How other modes use the file

Guard and Explore read the intent file before planning and check every deviation or direction against it:
- **weak**: change it and note the change.
- **medium**: case by case. Ask only when the change touches that exact area; otherwise list it among the deviations.
- **strong**: tell the user "the design of X will change" and wait for confirmation before building. If confirmed, update the entry.

When Guard amends a rule for an area, update that area's entry; a design the user just chose is medium unless they say otherwise.
