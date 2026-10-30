# AI Interaction Log (`AI_LOG.md`)

Use one entry per significant AI interaction. Copy this table into AI_LOG.md for each entry.

---

### Entry 1: Requirements & EARS Specification

| Field | Your entry |
| :--- | :--- |
| **Entry # / date** | 1 / Oct 29, 12:15 pm |
| **Tool, model, mode** | Antigravity, Gemini 3.8 Flash, Agent mode |
| **Slice** | Specification: Requirements & EARS Acceptance Criteria |
| **Prompt (verbatim or summarized)** | Formulate EARS-compliant requirements specification for Track C (Live Order Tracking MVP) based on MiniDash food-delivery API requirements. Define acceptance criteria (AC-1.1 through AC-5.4) covering tracking snapshot, status lifecycle, deterministic ETA, SSE stream, and driver simulator. |
| **What the AI produced** | `requirements.md` covering 5 functional areas, 20+ EARS criteria (Ubiquitous, Event-driven, State-driven, Unwanted behavior), data dictionaries, and non-functional requirements. |
| **What I verified** | Verified all criteria against course rubric. Confirmed terminal states (`DELIVERED`, `CANCELLED`) were immutable and that cancellation constraints were explicit. |
| **What I changed and why** | Refined AC-2.3 and AC-2.9 to explicitly distinguish HTTP 400 Bad Request (unrecognized status strings) from HTTP 409 Conflict (invalid lifecycle transitions), following REST best practices. |
| **Outcome** | Accepted and committed as `docs: add requirements specification for TrackC live order tracking (MVP)` (PR #1). |

---

### Entry 2: Architectural Design Document

| Field | Your entry |
| :--- | :--- |
| **Entry # / date** | 2 / Oct 29, 12:45 pm |
| **Tool, model, mode** | Antigravity, Gemini 3.8 Flash, Agent mode |
| **Slice** | Architectural Design (`design.md`) |
| **Prompt (verbatim or summarized)** | Create architectural design document for Track C adhering to MiniDash 3-layer architecture (routes -> service -> repository). Detail schema additions, SQLite migration strategy, FSM transition matrix, pure-function ETA calculation engine, in-memory broadcaster for SSE, and CLI simulator. |
| **What the AI produced** | `design.md` with ASCII/Mermaid state diagrams, SQL DDL with indexing, schema migration strategy, concurrency considerations (single-writer SQLite), and component interface definitions. |
| **What I verified** | Checked that no heavy external dependencies (Redis, Celery, or external message brokers) were introduced, keeping MiniDash zero-dependency beyond FastAPI/Uvicorn. Confirmed SQLite foreign key cascade behavior. |
| **What I changed and why** | Removed suggested Redis pub/sub queue; replaced with in-memory `asyncio.Queue` broadcaster to maintain project simplicity and zero-configuration local execution. |
| **Outcome** | Accepted and committed as `docs: add architectural design document for TrackC live order tracking` (PR #2). |

---

### Entry 3: Test-Driven Task Breakdown & Slices

| Field | Your entry |
| :--- | :--- |
| **Entry # / date** | 3 / Oct 29, 2:15 pm |
| **Tool, model, mode** | Antigravity, Gemini 3.8 Flash, Agent mode |
| **Slice** | Implementation Plan (`tasks.md`) |
| **Prompt (verbatim or summarized)** | Decompose Track C architectural design into incremental, test-driven vertical slices. Each slice must have a clear scope, acceptance criteria mapping, files touched, and explicit pytest commands. |
| **What the AI produced** | `tasks.md` with an 8-slice implementation roadmap, dependency graph, traceability matrix, and detailed test specifications for each slice. |
| **What I verified** | Walked through the dependency tree to ensure Slices 1 through 8 could be built and tested incrementally without circular dependencies or broken interim states. |
| **What I changed and why** | Reordered Slice 3 (ETA Engine) to precede Slice 4 (FSM) so order placement and status updates could immediately compute and persist deterministic ETAs. |
| **Outcome** | Accepted and committed as `docs: add implementation tasks and verification slices for TrackC live order tracking` (PR #3). |

---

### Entry 4: Slice 1 — Database Schema & Tracking Models

| Field | Your entry |
| :--- | :--- |
| **Entry # / date** | 4 / Oct 29, 10:15 pm |
| **Tool, model, mode** | Antigravity, Gemini 3.8 Flash, Agent mode |
| **Slice** | Slice 1: Database Schema & Tracking Data Models |
| **Prompt (verbatim or summarized)** | Implement database schema migration in `app/database.py` and tracking Pydantic schemas in `app/schemas/order.py`. Create `tests/test_schema.py` to verify table creation, columns, indexes, and schema serialization. |
| **What the AI produced** | DDL for `order_status_history`, idempotent SQLite column migration for `estimated_arrival_at` on `orders`, `OrderStatus` enum, `OrderTrackingResponse`, `TrackingHistoryItem` schemas, and `tests/test_schema.py`. |
| **What I verified** | Ran `.venv/bin/pytest tests/test_schema.py -v`. Checked SQLite schema via `sqlite_master` and `PRAGMA table_info`. |
| **What I changed and why** | Kept `OrderStatusUpdate.status` typed as `str` instead of `OrderStatus` enum in Pydantic so invalid statuses pass validation into the service layer, enabling an explicit HTTP 400 with a domain error message rather than Pydantic's generic 422 Unprocessable Entity. |
| **Outcome** | Accepted and committed as `feat(db): add tracking schema, migration, and order tracking models (Slice 1)` (PR #4). |

---

### Entry 5: Slice 2 — Initial Order Placement & History Entry

| Field | Your entry |
| :--- | :--- |
| **Entry # / date** | 5 / Oct 29, 10:28 pm |
| **Tool, model, mode** | Antigravity, Gemini 3.8 Flash, Agent mode |
| **Slice** | Slice 2: Initial Order Placement (`PLACED`) & History Entry |
| **Prompt (verbatim or summarized)** | Update `app/repository/order_repo.py` and `app/services/order_service.py` so order creation atomically sets `PLACED` status and records initial row in `order_status_history`. Ensure existing order tests in `tests/test_orders.py` continue to pass. |
| **What the AI produced** | Transactional order creation logic inserting into both `orders` and `order_status_history` within the same SQLite transaction. Added tests in `tests/test_orders.py`. |
| **What I verified** | Ran `.venv/bin/pytest tests/test_orders.py -v`. Verified transaction rollback by simulating an error during history insertion. |
| **What I changed and why** | Ensured timestamp generation uses standardized UTC ISO 8601 strings (`datetime.now(timezone.utc).isoformat()`) across repository operations. |
| **Outcome** | Accepted and committed as `feat(orders): initialize orders with PLACED status and atomic history entry (Slice 2)` (PR #5). |

---

### Entry 6: Slice 3 — Deterministic ETA Calculation Engine

| Field | Your entry |
| :--- | :--- |
| **Entry # / date** | 6 / Oct 29, 10:35 pm |
| **Tool, model, mode** | Antigravity, Gemini 3.8 Flash, Agent mode |
| **Slice** | Slice 3: Deterministic ETA Calculation Engine |
| **Prompt (verbatim or summarized)** | Create pure deterministic ETA calculation engine in `app/services/eta_calculator.py` and unit tests in `tests/test_eta.py` according to AC-3.1–3.5 rules (base prep time 10m + 3m per item + transit times per state). |
| **What the AI produced** | `calculate_eta` function and unit tests covering `PLACED`, `PREPARING`, `READY`, `PICKED_UP`, `DELIVERED`, and `CANCELLED`. |
| **What I verified** | Ran `.venv/bin/pytest tests/test_eta.py -v`. Tested edge cases with zero items, multiple items, and terminal states (delivering `None`). |
| **What I changed and why** | Added defensive validation to ensure non-positive item counts default gracefully or raise explicit `ValueError`, and ensured `CANCELLED` orders explicitly return `None` for ETA. |
| **Outcome** | Accepted and committed as `feat(orders): implement deterministic ETA calculation engine (Slice 3)` (PR #6). |

---

### Entry 7: Slice 4 — Finite State Machine (FSM) & Atomic Status Updates

| Field | Your entry |
| :--- | :--- |
| **Entry # / date** | 7 / Oct 29, 10:50 pm |
| **Tool, model, mode** | Antigravity, Gemini 3.8 Flash, Agent mode |
| **Slice** | Slice 4: Finite State Machine (FSM) & Atomic Status Updates |
| **Prompt (verbatim or summarized)** | Implement FSM lifecycle enforcement in `app/services/order_service.py` and `app/repository/order_repo.py` (`update_order_status`). Enforce valid forward transitions, cancellation rules, terminal state immutability, and atomic status history recording. Provide `tests/test_fsm.py`. |
| **What the AI produced** | State transition validation map, HTTP 400 for unrecognized statuses, 409 for invalid transitions, atomic update method in `order_repo.py`, and test suite in `tests/test_fsm.py`. |
| **What I verified** | Ran `.venv/bin/pytest tests/test_fsm.py -v`. Tested illegal skips (`PLACED` -> `PICKED_UP`), invalid cancellation (`PREPARING` -> `CANCELLED`), and modifications to `DELIVERED` orders. |
| **What I changed and why** | Explicitly recomputed ETA upon status transitions (e.g. `PICKED_UP` sets arrival time based on transit time) and ensured the updated ETA is atomically persisted in `orders.estimated_arrival_at`. |
| **Outcome** | Accepted and committed as `feat(orders): enforce FSM lifecycle transitions and atomic status updates (Slice 4)` (PR #7). |

---

### Entry 8: Slice 5 — Live Tracking Snapshot & Polling Endpoint

| Field | Your entry |
| :--- | :--- |
| **Entry # / date** | 8 / Oct 29, 11:35 pm |
| **Tool, model, mode** | Antigravity, Gemini 3.8 Flash, Agent mode |
| **Slice** | Slice 5: Live Tracking Snapshot & Polling Endpoint |
| **Prompt (verbatim or summarized)** | Implement `GET /orders/{order_id}/tracking` endpoint returning `OrderTrackingResponse` with current status, ETA, and chronological status history. Add test cases in `tests/test_tracking.py`. |
| **What the AI produced** | Tracking endpoint handler in `app/routes/order_routes.py`, `get_order_tracking` in `order_service.py` and repository query joining history. Test suite covering 200 OK and 404 Not Found. |
| **What I verified** | Ran `.venv/bin/pytest tests/test_tracking.py -v`. Verified history entries are ordered strictly chronologically by timestamp and `id`. |
| **What I changed and why** | Ensured repository query specifies `ORDER BY id ASC` to guarantee deterministic ordering even when timestamps occur in the same sub-second window. |
| **Outcome** | Accepted and committed as `feat(orders): live tracking snapshot and polling endpoint (Slice 5)` (PR #8). |

---

### Entry 9: Slice 7 — Driver Advancement Simulator CLI

| Field | Your entry |
| :--- | :--- |
| **Entry # / date** | 9 / Oct 29, 11:48 pm |
| **Tool, model, mode** | Antigravity, Gemini 3.8 Flash, Agent mode |
| **Slice** | Slice 7: Driver Advancement Simulator CLI |
| **Prompt (verbatim or summarized)** | Implement CLI script `scripts/simulate_driver.py` to advance an order through all remaining lifecycle stages to `DELIVERED` via HTTP PATCH calls with configurable delays. Provide unit/mock tests in `tests/test_simulator.py`. |
| **What the AI produced** | CLI script with argparse, HTTP client functions using standard library `urllib`, delay options, verbose status logging, and `tests/test_simulator.py`. |
| **What I verified** | Ran `.venv/bin/pytest tests/test_simulator.py -v`. Verified simulator handles 404, already-terminal orders, and network failures with appropriate error exit codes. |
| **What I changed and why** | Used Python standard library `urllib.request` instead of external `requests` or `httpx` to strictly adhere to the zero extra dependencies requirement. |
| **Outcome** | Accepted and committed as `feat(simulator): add driver advancement simulator CLI and test suite (Slice 7)` (PR #10). |

---

### Entry 10: Slice 6 — In-Memory Broadcaster & Server-Sent Events (SSE)

| Field | Your entry |
| :--- | :--- |
| **Entry # / date** | 10 / Oct 30, 8:50 am |
| **Tool, model, mode** | Antigravity, Gemini 3.8 Flash, Agent mode |
| **Slice** | Slice 6: In-Memory Broadcaster & Server-Sent Events (SSE) |
| **Prompt (verbatim or summarized)** | Implement `app/services/broadcaster.py` with an in-memory pub/sub event broadcaster using `asyncio.Queue`. Implement `GET /orders/{order_id}/tracking/stream` with `text/event-stream` returning initial snapshot and real-time updates on status changes, auto-closing on terminal states. |
| **What the AI produced** | `Broadcaster` singleton class, SSE streaming generator endpoint in `app/routes/order_routes.py`, integration in `update_order_status` to publish events, and `tests/test_sse.py`. |
| **What I verified** | Ran `.venv/bin/pytest tests/test_sse.py -v`. Verified immediate initial snapshot upon connection, event fan-out to multiple subscribers, and stream closure upon `DELIVERED` / `CANCELLED`. |
| **What I changed and why** | Handled client disconnect cleanup in a `finally` block to prevent lingering listeners in memory and queue memory leaks. |
| **Outcome** | Accepted and committed as `feat(sse): in-memory broadcaster and server-sent events stream (Slice 6)` (PR #9). |

---

### Entry 11: Slice 8 — End-to-End Tracking Lifecycle & Regression Suite

| Field | Your entry |
| :--- | :--- |
| **Entry # / date** | 11 / Oct 30, 9:02 am |
| **Tool, model, mode** | Antigravity, Gemini 3.8 Flash, Agent mode |
| **Slice** | Slice 8: End-to-End Tracking Lifecycle & Regression Suite |
| **Prompt (verbatim or summarized)** | Create end-to-end integration and regression suite in `tests/test_e2e_tracking.py` verifying full lifecycle progression (placed -> delivered), concurrent SSE listener receiving events, and ensuring existing baseline endpoints are not regressed. |
| **What the AI produced** | `tests/test_e2e_tracking.py` executing full order lifecycle and testing restaurants/menu/order regression endpoints. |
| **What I verified** | Ran `.venv/bin/pytest -v` across the entire test suite (47 passed in 0.61s). Checked test coverage across all slices. |
| **What I changed and why** | Adjusted async event gathering in the e2e test to coordinate with `broadcaster.publish` without race conditions or timeouts. |
| **Outcome** | Accepted and committed as `feat(test): add end-to-end tracking lifecycle and regression suite (Slice 8)` (PR #11). |
