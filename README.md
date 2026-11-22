# VoltKart Multi-Source Chat Assistant

A full-stack, grounded chat assistant that answers analytical questions from tabular CSV data, dated policies and job descriptions, and live web search — with strict numeric grounding, deterministic document version resolution, machine-verified citations, and an isolated SQL sandbox.

## Key Architecture Principles

1. **No Arithmetic in LLM**: All sums, counts, date math, sorting, and top-N filters are strictly computed via DuckDB SQL or Python code.
2. **Deterministic Version Resolution**: Document versions are resolved per fact in deterministic code — never a naive "newest document only" filter. If the latest version is silent on a queried clause, older versions are consulted with provenance disclosed.
3. **Machine-Verified Citations**: Every tabular claim is tied to executed SQL and result rows; every document claim includes file name, effective date, section/page, and a verbatim quote verified against indexed text.
4. **SQL Sandboxing**: Multi-layer security featuring single SELECT AST allowlisting (via `sqlglot`), read-only connections, and disabled external filesystem access.
5. **No Sample-Specific Hardcoding**: Application logic is completely decoupled from sample entity names, IDs, and column values (enforced by `make no-hardcode` and variant testing).

---

## Workspace Structure

```
├── assignment/              # Directory junction to sample bundle and specification
├── backend/                 # FastAPI backend, retrieval pipeline, SQL agent, resolver
├── frontend/                # React UI, evidence drawer, file library, chart renderer
├── tests/
│   ├── unit/                # Unit test suite (parsers, resolvers, sandbox, grounding)
│   ├── golden/              # Evaluation harness and ground truth (golden.yaml)
│   └── variants/            # Variant bundle generator (make_variant.py)
├── scripts/                 # Cross-platform runner and verification scripts
├── reports/                 # Verification runs and audit output
├── docs/                    # Architecture ADRs, risks catalog, progress tracking
└── evaluation/              # Live PDF exports and judge calibration logs
```

---

## Quickstart & Setup

### Prerequisites
- Python 3.12+ (tested with Python 3.12.16)
- Node.js 18+ (tested with v26.7.0)
- `make` (or use `python scripts/runner.py` directly on Windows)

### 1. Environment Setup
```bash
# Initialize virtual environment and install dependencies
make setup
# Or manually on Windows:
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env and supply GEMINI_API_KEY
```

---

## Verification & Commands

| Command | Purpose |
| :--- | :--- |
| `make setup` | Install dependencies into virtual environment |
| `make dev` | Start development server |
| `make verify` | Run full verification suite (lint, format, no-hardcode, unit, golden) and write report |
| `make lint` | Run code quality checks via Ruff |
| `make format` | Check/apply formatting via Ruff |
| `make no-hardcode` | Scan `backend/` and `frontend/src/` for forbidden sample entity strings |
| `make variants` | Generate full variant bundle with brand mutations and date shifts |
| `make test` | Run unit test suite |
| `make golden` | Run evaluation suite against `tests/golden/golden.yaml` |

---

## Project Status

- **Phase 0 (Orient & Plan)**: Complete. Architecture Decisions (ADR-001 through ADR-007), Design Specification (`DESIGN.md`), and Pre-mortem catalog (`docs/RISKS.md`) established.
- **Phase 1 (Skeleton & Truth Harness)**: Complete. Isolated virtual environment initialized, cross-platform runner (`scripts/runner.py`) built, golden evaluation harness (`tests/golden/test_golden.py`) configured with deterministic assertions, and RED BASELINE asserted.
