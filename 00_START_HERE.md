# Start here — 8 steps

## What's in this kit

| File | Where it goes | Purpose |
|---|---|---|
| `01_MASTER_PROMPT.md` | paste as the **first message** | Full spec, traps, architecture, verification system, phase plan |
| `02_PHASE_PROMPTS.md` | paste **one at a time** | Phase 1–8 prompts + utility prompts (fix loop, review, failure hunt, interview drill) |
| `AGENTS.md` | repo root | Always-on rules (7.2k chars; Antigravity's cap is 12k) |
| `REVIEW.md` | repo root | Review protocol (your template) + self-improving rules log, seeded with 24 predicted risks |
| `tests/golden/golden.yaml` | `tests/golden/` | Ground truth for the 20 eval questions + 10 adversarial probes |

## Steps

1. Create an empty repo folder. Unzip `ml-intern-assignment.zip` into it so you have `assignment/` (treat as read-only).
2. Copy `AGENTS.md`, `REVIEW.md` and `tests/golden/golden.yaml` into the repo, same paths.
3. **Skills (optional but recommended).** Read each skill's `SKILL.md` before installing it: skills are instructions your agent will obey.
   - `be-ambitious`: raw file `https://github.com/DannyMac180/skills/raw/refs/heads/main/be-ambitious/SKILL.md` → `.agents/skills/be-ambitious/SKILL.md`
   - `hallmark`: `npx skills add nutlope/hallmark` (if it doesn't list Antigravity as a target, copy its folder to `.agents/skills/hallmark/`)
   - `awwwards`: several different community skills use this name. Install the one you actually found, or skip it; the master prompt works without it.
   - `ponytail`: its core ladder is already inside `AGENTS.md`.
4. **Restart the Antigravity session** after adding skills so they are detected, then confirm with `ls .agents/skills`.
5. **Create a Gemini API key** in Google AI Studio for the *app* to use at runtime. This is separate from your Antigravity quota. It goes in `.env` (never in chat, never in git).
6. Open a fresh agent session in the repo. Paste `01_MASTER_PROMPT.md`. It stops after Phase 0 and waits for you.
7. Read the plan. Approve (or change) it using the approval message in `02_PHASE_PROMPTS.md`, then paste Phase 1, 2, 3… one at a time. Read each gate report's *Evidence* section before moving on.
8. Before Phase 8 ends, ask the agent where Antigravity keeps this project's session logs and back that folder up untouched.

## Only you can do these

- **Understand the code.** The live round is you explaining it. Use prompt **U5** (interview drill) regularly, and read `docs/EXPLAIN_ME.md` when it appears.
- **Record the video** (10–15 min, your voice, webcam on). `docs/VIDEO_SCRIPT.md` is an outline for you to speak, not something to read out.
- **Keep the AI session logs complete and unedited.** The brief says hiding AI use is penalised, using it is not.
- **Get any `NEEDS_FROM_HUMAN` books** through a library, publisher or author's site. The agent is told to use only legally free sources otherwise.

## If something goes wrong

- The agent says "done" without output → prompt **U1**.
- A test fails → prompt **U2**.
- New session / context lost → prompt **U6**.
