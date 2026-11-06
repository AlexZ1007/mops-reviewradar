---
version: 1
slug: "frontend-pages-1-projects-py"
primary_target: "frontend/pages/1_Projects.py"
related_targets: ["frontend/Home.py","frontend/pages/2_Project.py","frontend/pages/3_Notifications.py"]
---

Scope: all signed-in ReviewRadar screens plus sign-in (frontend/Home.py, pages/1_Projects.py, pages/2_Project.py, pages/3_Notifications.py, shared shell in ui.py). Mode: Operate.
Audience and job: product-team analysts and PMs, several times a week on a laptop; find a project, see their role, answer invitations, manage members (owners).
Constraints: Streamlit components plus injected CSS only; show only data the API returns (no invented metrics, member counts, or personal messages); crimson is the brand accent.
Chosen direction: Editor's Red Pencil (user choice, IMPECCABLE'S PICK card).
Memorable moment: the red pencil ring in the margin beside anything that needs your decision.

## Direction contract

THESIS: The workspace is a clean proof sheet; crimson is the editor's pencil and marks only what needs a decision or where you are. Refuses the sidebar-plus-card-grid dashboard and its decorative stats.

OWN-WORLD: White sheet, ink #1a1a1a, graphite #5f5b57 secondary text, hairline rule #e7e4e0, crimson #b0122b pencil. Source Serif 4 semibold for page titles and project names; Hanken Grotesk for all UI. Hairline-ruled rows, no shadows on panels, 6px control radius, Material Symbols icons.

STORY: The visitor sees where they are, what is waiting for their answer, and their role in each project, then acts in one click: open, accept, decline, invite, change a role.

FIRST VIEWPORT: 56px white top bar: wordmark left, Projects and Inbox (with count) as tabs with a crimson underline on the current one, account menu right. One 1040px column: serif title "Projects" with a one-line summary at left, crimson "New project" at right; pending invitations first, each with a crimson ring in the left margin; then the project list as hairline-ruled rows (name in serif, description, role).

FORM: Editor's Red Pencil, my rank 1 of 7 (pick card); seed:6ce23110aa6e77f6. Signature move: the pencil ring in the margin marking pending invitations and unread items; motion: the ring draws in once on load (stroke reveal), static under reduced motion.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
