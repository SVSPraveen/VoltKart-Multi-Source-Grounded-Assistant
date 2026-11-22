# ML Intern Take-Home Assignment: Multi-Source Chat Assistant

## Overview

Build a full-stack chat assistant that answers questions from uploaded tables, uploaded documents, and (optionally) the web, with a citation for every fact. You own all three layers: frontend, backend, and the AI pipeline.

The assistant serves a fictional electronics retailer, **VoltKart**. You will receive a sample bundle of interlinked CSV tables and dated company documents. Your system must work on this bundle and on any similar files a reviewer uploads.

Your submission is judged on your explainer video and the exported chat answers in your repository. Shortlisted candidates move to a live technical round.

## Provided files

The sample bundle `VoltKart_Sample_Bundle.zip` contains six interlinked CSV tables, eight dated documents, and a `DATA_DICTIONARY.md` describing keys and business definitions.

**Tables** (`tables/`): keys in one table appear in others, so most questions need joins across two or more tables.

| File | Contents | Links to |
| --- | --- | --- |
| stores.csv | 8 stores: city, region, manager | orders |
| customers.csv | 140 customers: home city, loyalty tier | orders |
| products.csv | 22 products: category, brand, list price | order\_items |
| orders.csv | 900 orders, Jan 2025 to Jun 2026 | customers, stores, order\_items |
| order\_items.csv | 1,329 line items: quantity, price, discount | orders, products, returns |
| returns.csv | 64 returns: reason, refund amount | order\_items |

**Documents** (`documents/`): several documents exist in more than one dated version, and versions conflict with each other. Each file carries its date in the file name and in the document body.

| Document family | Versions (format) |
| --- | --- |
| Return & Refund Policy | 2024-04-01 (PDF), 2025-01-15 (DOCX), 2025-09-01 (TXT) |
| Job Description: Machine Learning Engineer | 2025-03-10 (DOCX), 2025-10-20 (PDF) |
| VoltCare Extended Warranty Terms | 2024-07-01 (TXT), 2026-02-01 (DOCX) |
| Store Operations Notice | 2025-11-05 (PDF) |

Reviewers may test your system with additional files of the same kinds. Do not hard-code anything specific to these sample files.

## Functional requirements

Requirements are split into core and bonus. Finish every core requirement before starting any bonus one: a submission with all core requirements working correctly ranks above one with every bonus feature and wrong answers.

### Core (required)

1. **Chat interface.** A web UI where the user types messages and sees streamed or complete assistant responses, rendered as formatted text (markdown, tables, code).
2. **File upload.** The user can upload CSV, PDF, DOCX and TXT files from the UI. Uploaded files are listed in the UI and usable in the conversation. Uploading more files later must also work.
3. **Questions over related tables.** The assistant answers questions whose answers require combining data from two or more uploaded CSV tables. Answers must be numerically correct, not estimates.
4. **Questions over dated documents.** The assistant answers questions from uploaded documents. When multiple versions of a document state different values for the same fact, the answer must come from the version with the most recent document date. If a fact appears only in an older version, the assistant may answer from that version but must say which version it came from.
5. **Citations on every answer.** Every fact in an answer carries a citation shown in the UI:
   - Document facts: file name, document date, and page or section.
   - Table facts: the table(s) used and the computation or query that produced the value, viewable by the user.
   - If the assistant cannot find an answer in the provided sources, it must say so rather than invent one.
6. **Conversation memory.** Within a chat, the assistant remembers earlier turns and resolves follow-up questions such as "what about the second one?" Chat history must persist across a backend restart.
7. **Chat export.** A download button exports the current chat as a PDF. The PDF contains every user and assistant message in order with timestamps and the citations under each answer, plus any charts and the web search state per message if you build those bonus features.

### Bonus (optional)

8. **Web search toggle.** A UI toggle enables or disables web search per message. When off, the assistant must not use the web. When on, it can combine web results with uploaded data in one answer. Web facts are cited with source title and URL.
9. **Multiple chats.** The user can create new chats, see a list of existing chats, switch between them, and continue any earlier chat with its full history intact. Chats must not leak context into each other.
10. **Charts.** When asked for a chart (bar, line or pie at minimum), the assistant renders it inline in the chat from the underlying data, with axis labels and a title. Chart values must match the data and carry a citation like any other answer.

## Technical constraints

| Layer | Requirement |
| --- | --- |
| Frontend | Any framework or library of your choice |
| Backend | Python with FastAPI (required) |
| AI layer | Any libraries; LangChain or LangGraph preferred |
| LLM | Any provider, hosted or local, including free tiers |
| Web search | Any search API or tool |
| Storage | Any database or store; must survive a backend restart |

- The project must run locally from your README instructions on a fresh machine. A `docker compose up` setup is welcome but not required.
- Never commit API keys or secrets. Provide a `.env.example` listing every variable needed.
- You may use AI coding assistants. You must be able to understand and explain your code in the next round.

## Required evaluation questions

Run every question below in your app with the sample bundle uploaded, using the exact wording and the chat shown in brackets. Export each chat with your export button and commit the PDFs to an `evaluation/` folder in your repository (`chat1.pdf`, `chat2.pdf`, `chat3.pdf`). Reviewers grade these exported answers and citations. You do not need to show these questions in your video.

Questions marked bonus test bonus features: skip any whose feature you did not build. Without multiple chats, run all questions in a single chat and export it as `chat1.pdf`.

**A. Tables (Chat 1)**

1. Which store had the highest revenue in 2025, and who manages it?
2. Who were the top 3 customers by spend at that store in 2025? *(follow-up; must use memory)*
3. Which product was returned most often, and what is its most common return reason?
4. How many Platinum customers whose home city is Bengaluru bought a laptop in Q1 2026? Name them.
5. What is the total refund amount by region?

**B. Documents (Chat 2)**

6. What is the return window for Gold members?
7. How many business days does a refund take?
8. How soon must a customer report a product damaged on delivery?
9. Are opened earbuds returnable?
10. What is the location, work mode and salary range for the Machine Learning Engineer role?
11. Who does the Machine Learning Engineer report to?
12. How much does VoltCare cost, and is there a limit on the number of claims?

**C. Tables and documents together (Chat 2)**

13. Kavya Kapoor wants to return the phone from order O00174, 12 days after delivery. Is that allowed, and would a restocking fee apply if it were within the window?
14. The store operations notice says one store was closed in December 2025. Does the order data agree with that?

**D. Charts (Chat 1, bonus)**

15. Show a bar chart of total revenue by product category for 2025.
16. Show a line chart of smartphone units sold per month in 2025.

**E. Web search (Chat 3, bonus)**

17. With web search **off**: What is Amazon India's return window for smartphones?
18. Turn web search **on** and ask the same question, then: How does that compare with VoltKart's smartphone return window?

**F. Multiple chats (Q19 bonus) and persistence (Q20 core)**

19. Switch from Chat 2 back to Chat 1 and ask: Show the result of my first question as a bar chart of the top 5 stores.
20. Restart the backend, reopen Chat 2, and ask: Summarize what we discussed so far.

## Deliverables

Submit three things: a code repository, a README, and an explainer video.

**1. Repository.** A public GitHub repository (or private with reviewer access) containing frontend, backend and AI code, with a meaningful commit history, plus the evaluation/ folder of exported chat PDFs.

**2. README**, covering:

- Setup and run steps, from clone to working app
- Architecture overview with a diagram
- How each requirement you built is met, and which bonus features you attempted
- Known limitations and what you would improve with more time

**3. Explainer video**, 10 to 15 minutes, screen recording with your voice and webcam on. It must cover, in this order:

1. A 1-minute intro: who you are and what you built.
2. Live walkthrough of the full application in one continuous take, starting from an empty app with no files uploaded, covering every requirement you built with questions of your own.
3. Architecture walkthrough: how a question flows from the UI to the answer, using your diagram.
4. Code walkthrough of how you handle table joins, document versions, citations, memory and chat export.
5. One design decision you made, the alternative you rejected, and why.
6. Where your system fails or gives wrong answers, shown with at least one real example.

Edited cuts are allowed only between the six parts above, not inside the live walkthrough. Upload the video unlisted on YouTube, Loom or Google Drive with view access.

## AI coding assistant logs

Preserve the full, unedited session logs from any AI coding tools you use (Claude Code, Cursor, Copilot Chat, ChatGPT or others). Do not submit them. If you are shortlisted, you will open them during the live round and walk the interviewer through how you used the tool.

- Keep every session from start to finish; do not delete, trim or rewrite them.
- Using AI tools is not penalized. Hiding their use is.
- If you used no AI tools, say so at the start of the live round.
