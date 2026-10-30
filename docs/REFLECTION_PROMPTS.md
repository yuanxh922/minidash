# CSCI-665 Software Engineering · MiniDash Assignment
## Section 7: Reflection Prompts

**Course**: CSCI-665 Software Engineering  
**Project**: MiniDash — Track C: Live Order Tracking & Driver Simulation (MVP)  
**Student**: Xiaohong Yuan (`xyuan04@nyit.edu`)  
**Student ID**: 1360530  

---

### 1. Three Defects

> *Describe three specific problems in AI output (wrong, risky, or wasteful). For each: what it was, how you found it, and how you fixed it.*

#### Defect 1: Scope Creep & Unrequested Heavy Infrastructure (Wasteful / Risky)
* **What it was**: During the initial architectural design phase (`design.md`) and Slice 6 planning for Server-Sent Events (SSE), the AI proposed incorporating an external Redis Pub/Sub message broker and a Celery worker queue, introducing heavy third-party dependencies (`redis-py`, `celery`) and external daemon process orchestration.
* **How I found it**: Architectural review of `design.md` against project constraints. MiniDash is an educational, self-contained REST API designed for zero-configuration local execution and testing without external service dependencies.
* **How I fixed it**: Explicitly rejected external brokers. Designed and implemented an in-memory, thread-safe asynchronous pub/sub broadcaster class (`Broadcaster` in `app/services/broadcaster.py`) using Python's native `asyncio.Queue`. This fulfilled all real-time SSE streaming requirements with sub-millisecond dispatch and zero external dependencies.

#### Defect 2: Schema Validation Interception Violating Domain Contract (Wrong / Risky)
* **What it was**: In Slice 1 (`app/schemas/order.py`) and Slice 4 (`order_service.py`), the AI initially typed `OrderStatusUpdate.status: OrderStatus` (a Pydantic Enum). When an unrecognized status string (e.g., `"OUT_FOR_DELIVERY"`) was sent to `PATCH /orders/{id}/status`, Pydantic's request-body validation intercepted the input and automatically returned HTTP `422 Unprocessable Entity`.
* **How I found it**: Automated test verification against acceptance criterion **AC-2.9** (*"If the requested status is not a recognized OrderStatus enum value, MiniDash shall respond with HTTP 400 Bad Request"*). The test failed because the API returned HTTP 422 instead of HTTP 400.
* **How I fixed it**: Changed `OrderStatusUpdate.status` to type `str` so raw input passes Pydantic validation into `OrderService.update_order_status`. In the service layer, explicit domain logic validates the string against `OrderStatus.__members__`, raising HTTP `400 Bad Request` with an informative error message for unrecognized statuses, and HTTP `409 Conflict` for invalid FSM transitions.

#### Defect 3: Non-Deterministic Ordering in Status History Queries (Wrong / Subtle)
* **What it was**: In Slice 5 (`GET /orders/{id}/tracking`), the AI wrote the SQL query fetching tracking history as:
  ```sql
  SELECT status, timestamp FROM order_status_history WHERE order_id = ? ORDER BY timestamp ASC;
  ```
  Because automated integration tests and the driver simulator advance order states rapidly in sub-second intervals, sequential transitions shared identical timestamp strings in SQLite's ISO text format. SQLite consequently broke ties using internal rowid or physical page order, causing sporadic non-chronological sorting.
* **How I found it**: Intermittent flaky test failures in rapid driver simulation assertions when verifying that history transitioned strictly `PLACED -> PREPARING -> READY -> PICKED_UP -> DELIVERED`.
* **How I fixed it**: Updated the query to `ORDER BY id ASC` and verified the index `idx_order_status_history_order_id`. Because `id` is an auto-incrementing integer primary key, it guarantees strictly monotonic chronological ordering across all status transitions regardless of clock resolution.

---

### 2. Where AI Helped Most and Least

> *Give one example of each and say why.*

#### Where AI Helped Most: Test Scaffolding & Combinatorial Boundary Case Generation
* **Example**: Authoring the comprehensive 47-test automated verification suite, particularly `tests/test_fsm.py` (finite state machine transitions) and `tests/test_eta.py` (deterministic ETA calculations).
* **Why**: The FSM lifecycle contains a transition matrix of 6 distinct states ($6 \times 6 = 36$ potential state pairs), plus conditional cancellation permissions, terminal state immutability rules, and HTTP error code branches (400 vs. 404 vs. 409). Hand-writing boilerplate test fixtures, mock SQLite connections, and parameterized assertions for every permutation is time-consuming and prone to human omission. The AI excelled at translating formal EARS acceptance criteria into thorough, edge-case-heavy test suites with clear assertion messaging, ensuring complete regression safety across all 8 slices.

#### Where AI Helped Least: Multi-Step Async Concurrency & Generator Lifecycles
* **Example**: Implementing the Server-Sent Events (SSE) streaming endpoint with client disconnect detection (`GET /orders/{id}/tracking/stream`) in Slice 6.
* **Why**: The AI struggled with asynchronous generator lifecycles and Starlette streaming protocol subtleties. Its initial output implemented a blocking polling loop (`while True: await asyncio.sleep(1)`) that repeatedly re-queried SQLite rather than reacting to push notifications. Furthermore, it failed to handle `asyncio.CancelledError` or client disconnections, creating lingering queue references and memory leaks. Human engineering intervention was required to design the listener subscription pattern, `asyncio.Queue` push/pull semantics, and guaranteed cleanup via `try...finally`.

---

### 3. Prompting Progression Across Slices

> *What did you change about how you prompted between your first and last slice?*

* **Early Slices (Slices 1 & 2)**: Prompts were conversational and goal-oriented (e.g., *"Implement the database schema and models for tracking"*). This prompted the AI to make unwarranted architectural assumptions: importing unrequested libraries, hallucinating unnecessary helper modules, and defaulting to standard Pydantic validation patterns that violated specific assignment HTTP error code contracts.
* **Later Slices (Slices 6, 7 & 8)**: Prompting evolved into a **rigorous contractual specification approach**:
  1. **Strict File & Scope Boundaries**: Prompts explicitly dictated files to touch and prohibited external libraries (*"Modify only `app/services/broadcaster.py` and `app/routes/order_routes.py`. Do NOT add dependencies to `requirements.txt`. Use standard library `urllib` only for CLI script"*).
  2. **EARS Acceptance Criteria Binding**: Prompts directly referenced requirements (*"Must satisfy AC-4.1, AC-4.2, and AC-4.4: return 200 with `text/event-stream`, emit initial snapshot immediately, auto-close on terminal status `DELIVERED` or `CANCELLED`"*).
  3. **Pre-emptive Failure Mode Constraints**: Prompts explicitly instructed how to handle edge cases before code was written (*"Wrap consumer queue in `try...finally` to ensure `broadcaster.unsubscribe` is called on client disconnect"*).
* **Impact**: Contract-first, boundary-constrained prompting eliminated scope creep and reduced iteration cycles from multiple manual correction rounds to single-shot passing code that satisfied all verification tests immediately.

---

### 4. A Decision You Did Not Delegate

> *Name one design or quality decision you kept for yourself and explain why.*

* **The Decision**: **Transactional FSM Invariants & Database Rollback Strategy (Single-Source-of-Truth Lifecycle Integrity)**.
* **Explanation**: The AI repeatedly suggested performing state transition checks in Python application memory prior to executing an independent `UPDATE orders` statement, followed by an independent `INSERT INTO order_status_history` query without explicit database-level transaction demarcation.
* **Why I kept it for myself**: State machines in web applications cannot rely on naive, non-atomic application-level checks. If an update to `orders` succeeds but the subsequent insert to `order_status_history` crashes (e.g., disk I/O failure, constraint violation, or server termination), the system enters an illegal, corrupted state where an order has transitioned status without an audit record. I deliberately designed and enforced the transaction boundary:
  1. Status updates and history recordings are wrapped in an atomic SQLite transaction (`BEGIN IMMEDIATE ... COMMIT / ROLLBACK`).
  2. If any step fails, the entire transition is aborted cleanly, leaving persistent state intact.
  3. Terminal states (`DELIVERED`, `CANCELLED`) are treated as immutable mathematical sinks enforced at the service boundary.
* **Engineering Rationale**: Architectural integrity, fault domains, and transactional boundaries are non-delegable engineering responsibilities. LLMs optimize for syntactic completion of the happy path, whereas robust software engineering demands defensive design against partial failure modes.

---

### 5. Limits of Your Evidence

> *What is still not verified in your feature, and how would you check it with more time?*

* **What is still not verified**:
  1. **Multi-Worker ASGI Concurrency & Distributed Event Delivery**: The current SSE broadcaster relies on an in-process, in-memory `asyncio.Queue`. When deploying FastAPI with multiple worker processes (e.g., `uvicorn app.main:app --workers 4`), orders updated in Worker A will not trigger SSE events for client connections handled by Worker B.
  2. **High-Throughput SQLite Write Contention (`SQLITE_BUSY`)**: Under the automated test suite, orders are processed sequentially or in small batches. Under intense concurrent write traffic from dozens of simultaneous driver simulations, SQLite's single-writer model could experience lock contention and write timeouts.
  3. **Transient Network Disconnection & Event Replay (Last-Event-ID)**: If a client's mobile network drops for 5 seconds and reconnects, the current SSE implementation emits the current snapshot upon reconnection, but does not replay intermediate transient status transitions that occurred during the outage window.
* **How I would check with more time**:
  1. **Multi-Process Concurrency Test**: Configure a multi-worker Uvicorn test harness with a Redis or shared IPC broadcaster backend, and write a concurrent client simulation to verify cross-worker event delivery.
  2. **Load & Contention Benchmarking**: Execute a Locust or `wrk` load test simulating 500 concurrent drivers advancing order statuses simultaneously to measure SQLite lock wait latency, p99 response times, and verify zero unhandled `sqlite3.OperationalError: database is locked` exceptions.
  3. **Network Chaos Testing**: Use Toxiproxy to inject random latency, packet drops, and socket termination into active SSE streams, asserting that clients recover with proper reconciliation.
