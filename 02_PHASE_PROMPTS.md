# Phase prompts — paste one at a time, after the master prompt

Rhythm: **master prompt → Phase 0 → you approve → Phase 1 → Phase 2 …** Each phase ends with a gate report. Read it (the *Evidence* section especially), then paste the next prompt.
If a gate report says "done" but shows no real command output, reply with prompt **U1**.

---

## After Phase 0: approval message

```
Plan approved, with these changes: [write them, or "none"].
Proceed to Phase 1. Re-read REVIEW.md first. Apply be-ambitious: deeper, not bigger.
Remember: no application code outside the phase's scope, and show real command output in the gate report.
```

## Phase 1 — Skeleton and truth harness

```
Phase 1: skeleton and truth harness.
Build the repo scaffold, Makefile, lint/type/test config, and `make verify` that prints one summary table and writes reports/verify-<timestamp>.md.
Wire tests/golden/golden.yaml into an eval harness (loader + deterministic assertions: numeric tolerance 0.01, entities, citation fields, version statement, abstention).
Build tests/variants/make_variant.py and `make no-hardcode`. Add the .gitignore, .env.example skeleton and a minimal README stub.
The golden evals must exist and FAIL right now (red baseline) - show me that failure output.
Re-derive 3 golden table numbers independently in a throwaway script and show they match.
Small conventional commits. Then the gate report.
```

## Phase 2 — Ingestion and storage

```
Phase 2: ingestion and storage (spec section 7.1).
Tables -> DuckDB with profiling, inferred relationships, schema card, and automatic inclusion of data documentation text.
Documents -> structure-aware extraction (PDF pages, DOCX headings and tables, TXT), tolerant date extraction with source recorded, version families, chunks, FTS5, local embeddings.
Idempotent uploads, ingestion summary API + UI card, graceful errors for every edge case in REVIEW R-023.
Prove with output: the ingestion summary for the sample bundle (all 8 documents with detected dates and families; all 6 tables with inferred relationships),
unit tests for every date format, and a restart test showing data survives.
Run `make verify`, run the Review Protocol on the diff, fix, re-verify, then the gate report.
```

## Phase 3 — Table QA

```
Phase 3: table question answering (spec section 7.2).
Implement the plan -> SQL -> validate -> execute -> check -> self-correct -> compose -> cite loop with the layered SQL sandbox (REVIEW R-009), numeric grounding (R-003), fan-out reconciliation (R-020).
Run golden Q1-Q5 live, 3 times each. Show the per-question table: pass/fail per run, the SQL produced, and the exact numbers vs golden.
Then try to break it: adversarial probes A6, A7, A8, A9, A10. Show results.
If anything fails: root-cause it, fix it, add a regression test and a REVIEW.md rule, re-run. Gate report with all of that.
```

## Phase 4 — Document QA with versions

```
Phase 4: document question answering with version resolution (spec section 7.3). This is the heart of the project.
Retrieval across ALL versions + sibling expansion, per-version structured extraction, quote verification, deterministic resolver, fallback disclosure.
Unit-test the resolver on synthetic families: newest silent, newest states, tie dates, undated, three versions with a changed fact.
Run golden Q6-Q12 live, 3 times each. For Q8, Q9, Q11, Q12 show the evidence drawer data: which version answered, which were superseded, whether the answer text names the version.
Also run probes A1, A2, A3, A4, A5 and the injection fixtures.
Failures -> root cause, fix, regression test, REVIEW rule. Gate report.
```

## Phase 5 — Core chat product

```
Phase 5: the core product (spec sections 7.4 - 7.7, 8, 9).
Streaming API (status events live, final answer after verification), contextualise step + resolved-entities memo + "Interpreted as", mixed questions (Q13, Q14), persistence across restart,
the UI (thread, evidence drawer, files library with version families, composer, ingestion summary cards) built from DESIGN.md, and PDF export (ReportLab + embedded Unicode font).
Before UI code: re-read DESIGN.md and AGENTS.md section 4. After UI code: Playwright screenshots at 360/768/1280/1920 and critique them honestly against DESIGN.md.
Export: parse the PDF text AND rasterise a page and look at the rupee sign.
Run golden Q1-Q14 and the core part of Q20 live, 3 times each. This is the CORE COMPLETE gate: no bonus work until every core question passes 3/3.
Review Protocol on the diff, fix, re-verify, gate report.
```

## Phase 6 — Bonus

```
Phase 6: bonus features, in this order: B9 multiple chats, B10 charts, B8 web search (spec section 7.8). Core must stay green throughout - re-run the core golden suite after each bonus.
B9: isolation test with a planted marker phrase. B10: chart specs reference stored query rows; test that a hand-edited value is rejected; export re-renders charts.
B8: server-side tool gating; test that Q17 (web off) makes ZERO outbound search calls; Tavily if a key exists, otherwise keyless fallback; fetch and read pages for factual claims; cite title + URL + retrieved-at.
Run golden Q15-Q19 live, 3 times each (Q17/Q18 need real network - tell me if that's unavailable).
Review Protocol on each bonus diff. Gate report.
```

## Phase 7 — Hardening

```
Phase 7: hardening. Run the full V0-V7 stack.
1) Variant bundles: generate at least 3 different variants (including a policy whose windows are in a table, a version that omits a fact, mixed date formats, different file format per version) and show answers vs pandas recomputation.
2) Adversarial: all probes + weird uploads + injection fixtures.
3) Security review: run the Review Protocol over the WHOLE codebase, in a fresh conversation if possible, with context "internet-reachable FastAPI app that executes LLM-written SQL on user-uploaded files".
4) Judge: calibrate first (>= 5 wrong answers, must flag >= 4), then run it on golden outputs.
5) UI: run `hallmark audit` (read-only) and axe-core; look at the screenshots; list what still looks generic and fix the top issues.
Fix every S1/S2. Show before/after evidence. Gate report.
```

## Phase 8 — Release

```
Phase 8: release.
README (setup, Mermaid architecture diagram, requirement -> implementation table, bonuses attempted, limitations, improvements, Windows notes, free-tier privacy note), .env.example complete, docs/ARCHITECTURE.md, KNOWN_LIMITATIONS.md with at least two REAL reproduced failures,
EXPLAIN_ME.md, VIDEO_SCRIPT.md. Then produce evaluation/chat1.pdf, chat2.pdf, chat3.pdf THROUGH THE UI export button with a Playwright script, in the order in the master prompt section 14, including the backend restart before Q20.
Open each PDF (extract text and rasterise pages) and verify timestamps, citations, charts, rupee signs and web-search state per message.
Run `make fresh-clone-test` and fix the README until it works untouched. Final report: what is proven, what is not, what could still be wrong.
```

---

# Utility prompts

## U1 — "Show me the evidence"
```
Your report claims success but doesn't show real command output. Re-run the relevant commands now and paste the actual, unedited output (trim only repeated lines).
If anything can't be run, say NOT RUN and why. Don't summarise results you haven't shown.
```

## U2 — Fix loop when something fails
```
Something is failing: [paste output or name the test].
Think it through before touching code: 1) reproduce it with the smallest failing input, 2) find the root cause (not the symptom), 3) list at least two possible fixes and pick the simplest that fixes the CLASS of bug,
4) implement it, 5) add a regression test, 6) append a rule to REVIEW.md, 7) run `make verify` and show the output, 8) run the Review Protocol on the fix diff and report.
Do not weaken or edit a golden expectation to make it pass.
```

## U3 — Review pass (fresh conversation, only the diff + REVIEW.md)
```
Read REVIEW.md. Then:

<context>This change is meant to [goal]. It runs in [environment].</context>
<diff>[paste git diff]</diff>

Review for bugs, missing edge cases and security problems. Skip style preferences.
For each finding, give the file and line, what breaks, the input that triggers it, and a suggested fix.
Rank by severity. If you find nothing serious, say so and do not pad the list.
```

## U4 — Hunt for real failures (feeds the video's "where it fails" section and KNOWN_LIMITATIONS)
```
Try to break the finished app on purpose. Invent 25 realistic questions a skeptical reviewer would ask over the sample bundle and over a variant bundle:
paraphrases of the golden questions, vague questions, questions mixing tables and policy, questions about dates before/after documents, questions needing two documents, questions the data can't answer, typos, follow-ups of follow-ups.
For each wrong, unsupported or shaky answer: save the input, the app's output, the correct answer (computed independently), the root cause. Rank by how embarrassing it would be.
Don't fix them yet. Give me the list, then propose which 2-3 to document as known limitations and which to fix.
```

## U5 — Interview drill for the live round
```
Act as a skeptical senior interviewer who has read this repository. Ask me one question at a time about my code: table joins, document version resolution, citations, memory, PDF export, and one design decision I rejected an alternative for.
After each of my answers, tell me what was right, what was wrong or vague, and what the code actually does (point to the file and function). Start with the hardest question about version resolution.
Keep going until I say stop. Never let me bluff: if I'm wrong, say so and show the code.
```

## U6 — Resume after a context reset or a new session
```
New session. Read AGENTS.md, REVIEW.md, docs/SPEC.md, docs/PROGRESS.md, then `git log --oneline -20` and `git status`.
Tell me in 8 lines: where we are, what's verified, what's open, the next step. Then run `make verify` and show the output before doing anything else.
```

## U7 — Ask for a taste check before the UI is "done"
```
Show me the UI as screenshots at 360 / 768 / 1280 / 1920 px for: empty app, after upload, a table answer with the evidence drawer open, a document answer with the version timeline, an abstention, an error.
Critique them yourself against DESIGN.md and the hallmark gates first: list what still looks templated or AI-generic. Fix the worst three. Show the new screenshots.
```
