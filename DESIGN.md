# DESIGN.md — UI/UX Design System Specification

## 1. Aesthetic Direction: The Calm Editorial Instrument-Panel

VoltKart Multi-Source Assistant is an evidence-first technical workspace, not an AI playground. It avoids flashy AI clichés (no purple-to-blue gradients, no frosted glassmorphism, no floating decorative blobs, no emoji as functional icons).

Instead, it embodies the precision of a high-density financial or intelligence terminal combined with the clean typography of an editorial broadsheet.

---

## 2. Design Tokens

### Color Palette
- **Paper Background (`bg-paper`):** `#FDFCF7` (warm, natural parchment)
- **Surface / Card (`bg-surface`):** `#F5F3EC` (subtle contrast against background)
- **Border / Hairlines (`border-subtle`):** `#E5E2D9` (crisp 1px borders)
- **Text Primary (`text-primary`):** `#111827` (deep rich ink)
- **Text Secondary (`text-muted`):** `#4B5563` (slate gray for metadata and quiet timestamps)
- **Brand / Accent ("Volt"):** `#D4E815` (sharp, vibrant yellow-green; used sparingly for active filters, evidence pill tags, and focus rings)
- **Alert / Error (`text-danger`):** `#DC2626`
- **Success / Verified (`text-success`):** `#059669`

### Typography
- **Primary Interface Font:** `Inter` / System UI fallback (self-hosted WOFF2, offline capable)
- **Data & Numeric Font:** System tabular numerals via CSS:
  ```css
  font-feature-settings: 'tnum' 1, 'zero' 1;
  ```
- **Code & Query Font:** `JetBrains Mono` / `Fira Code` / `monospace` for SQL statements, formulas, and JSON evidence blocks.

### Layout Geometry
- **Left Sidebar (260px):** Chat Sessions list + Versioned Files Library (grouped by version families).
- **Center Thread (flexible, max-w-4xl):** Clean conversational message stream with subtle "Interpreted as: ..." context tags and inline citation badges `[1]`, `[2]`.
- **Right Evidence Drawer (380px, collapsible):**
  - **For Table Answers:** Active SQL query with syntax highlighting, copy-to-clipboard action, and a tabular preview of the first 50 rows.
  - **For Document Answers:** A **Version Timeline** showing which version stated the fact, superseded older versions, and a machine-verified quote excerpt.

---

## 3. Component Hierarchy & Micro-Interactions

### 1. Inline Citation Badges
Numbered superscript or compact pills (e.g., `[Doc: Return Policy v2]`, `[Table: orders + 2]`). Clicking an inline citation opens the Evidence Drawer directly focused on that specific proof card.

### 2. Ingestion Summary Cards
Immediately upon uploading a batch of files, the chat presents a structured summary card:
- Tables: Row count, column names, inferred primary/foreign keys.
- Documents: Title, detected document date with provenance, version family grouping, section count.

### 3. "Interpreted As" Quiet Line
When a conversational turn includes entity resolution or implicit timeframes (e.g., "what about that store?"), a quiet, muted note appears above the answer:
`Interpreted as: store_id = 'S04', year = 2025`

### 4. Accessibility & Responsiveness
- High contrast compliant with WCAG 2.1 AA standards.
- Visible focus outlines (`focus-visible:ring-2 focus-visible:ring-[#D4E815]`).
- Strict adherence to `prefers-reduced-motion`: transitions collapse to instant state changes when reduced motion is preferred.
- Responsive breakpoints tested across 360px (mobile), 768px (tablet), 1280px (laptop), and 1920px (desktop).

