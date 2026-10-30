#!/usr/bin/env python3
"""MiniDash Driver Advancement Simulator CLI.

Sequentially advances an order through remaining lifecycle states:
PLACED -> PREPARING -> READY -> PICKED_UP -> DELIVERED
with configurable delays and formatted console logs.
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional, Sequence

PROGRESSION = ["PLACED", "PREPARING", "READY", "PICKED_UP", "DELIVERED"]
TERMINAL_STATES = {"DELIVERED", "CANCELLED"}


def _http_request(
    method: str, url: str, body: Optional[dict] = None
) -> tuple[int, dict]:
    """Send an HTTP request via standard library urllib and return (status_code, response_dict)."""
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req) as resp:
            status_code = resp.status
            content = resp.read()
            resp_body = json.loads(content.decode("utf-8")) if content else {}
            return status_code, resp_body
    except urllib.error.HTTPError as exc:
        content = exc.read()
        try:
            resp_body = json.loads(content.decode("utf-8")) if content else {}
        except Exception:
            resp_body = {"detail": content.decode("utf-8", errors="replace")}
        return exc.code, resp_body
    except Exception as exc:
        return 0, {"detail": str(exc)}


def run_simulation(
    order_id: int, delay: float = 3.0, base_url: str = "http://127.0.0.1:8000"
) -> int:
    """Simulate driver advancement for a designated order through to DELIVERED.

    Args:
        order_id: The ID of the target order to advance.
        delay: Delay in seconds between consecutive transitions (default 3.0).
        base_url: MiniDash API server base URL.

    Returns:
        0 if simulation reached DELIVERED successfully, 1 otherwise.
    """
    base_url = base_url.rstrip("/")
    tracking_url = f"{base_url}/orders/{order_id}/tracking"

    status_code, tracking_data = _http_request("GET", tracking_url)
    if status_code != 200:
        print(
            f"Error: Failed to fetch tracking for order {order_id} (HTTP {status_code}): "
            f"{tracking_data.get('detail', tracking_data)}",
            file=sys.stderr,
        )
        return 1

    current_status = tracking_data.get("current_status")
    if current_status in TERMINAL_STATES:
        print(
            f"Order {order_id} is already in terminal state '{current_status}'. Simulation aborted.",
            file=sys.stderr,
        )
        return 1

    if current_status not in PROGRESSION:
        print(
            f"Error: Order {order_id} has invalid or unrecognized status '{current_status}'.",
            file=sys.stderr,
        )
        return 1

    current_idx = PROGRESSION.index(current_status)
    remaining_states = PROGRESSION[current_idx + 1 :]

    if not remaining_states:
        print(f"Order {order_id} has no remaining advancement states.")
        return 0

    patch_url = f"{base_url}/orders/{order_id}/status"
    for next_status in remaining_states:
        if delay > 0:
            time.sleep(delay)

        status_code, patch_data = _http_request(
            "PATCH",
            patch_url,
            body={"status": next_status},
        )
        if status_code != 200:
            print(
                f"Error: Failed to advance order {order_id} to {next_status} (HTTP {status_code}): "
                f"{patch_data.get('detail', patch_data)}",
                file=sys.stderr,
            )
            return 1

        now_str = datetime.now(timezone.utc).isoformat()
        eta = patch_data.get("estimated_arrival_at") or "None"
        print(f"[{now_str}] Order {order_id} advanced to {next_status} (ETA: {eta})")

    print(f"Order {order_id} successfully reached DELIVERED.")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint for simulate_driver."""
    parser = argparse.ArgumentParser(
        description="Simulate driver advancement for a MiniDash order through to DELIVERED."
    )
    parser.add_argument(
        "--order-id",
        type=int,
        required=True,
        help="ID of the order to advance",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Delay in seconds between status transitions (default: 3.0)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="Base URL of the MiniDash server (default: http://127.0.0.1:8000)",
    )

    args = parser.parse_args(argv)
    return run_simulation(
        order_id=args.order_id, delay=args.delay, base_url=args.base_url
    )


if __name__ == "__main__":
    sys.exit(main())
