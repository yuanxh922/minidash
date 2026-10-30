import pytest
from typing import Optional

from scripts import simulate_driver


def _create_order(client, restaurant_id: int = 1) -> dict:
    payload = {
        "restaurant_id": restaurant_id,
        "address": "123 Elm Street",
        "items": [
            {"menu_item_id": 1, "quantity": 1},
        ],
    }
    response = client.post("/orders", json=payload)
    assert response.status_code == 201
    return response.json()


def _make_fake_http_request(client, patch_tracker: Optional[list] = None):
    def fake_http_request(
        method: str, url: str, body: Optional[dict] = None
    ) -> tuple[int, dict]:
        if method.upper() == "PATCH" and patch_tracker is not None:
            patch_tracker.append(body.get("status") if body else None)
        res = client.request(method=method, url=url, json_body=body)
        try:
            data = res.json()
        except Exception:
            data = {}
        return res.status_code, data

    return fake_http_request


def test_simulator_advances_placed_order_to_delivered(monkeypatch, client):
    """Places order in PLACED, monkeypatches _http_request, runs simulation to DELIVERED."""
    order = _create_order(client)
    order_id = order["id"]
    assert order["status"] == "PLACED"

    fake_req = _make_fake_http_request(client)
    monkeypatch.setattr(simulate_driver, "_http_request", fake_req)

    rc = simulate_driver.run_simulation(
        order_id=order_id, delay=0.01, base_url="http://test"
    )
    assert rc == 0

    tracking_res = client.get(f"/orders/{order_id}/tracking")
    assert tracking_res.status_code == 200
    tracking_data = tracking_res.json()
    assert tracking_data["current_status"] == "DELIVERED"

    history = tracking_data["history"]
    assert len(history) == 5
    expected_statuses = ["PLACED", "PREPARING", "READY", "PICKED_UP", "DELIVERED"]
    assert [item["status"] for item in history] == expected_statuses


def test_simulator_partial_advancement_from_ready(monkeypatch, client):
    """Sets order to READY, runs simulation, asserts only 2 remaining steps executed."""
    order = _create_order(client)
    order_id = order["id"]

    res_prep = client.patch(f"/orders/{order_id}/status", json={"status": "PREPARING"})
    assert res_prep.status_code == 200
    res_ready = client.patch(f"/orders/{order_id}/status", json={"status": "READY"})
    assert res_ready.status_code == 200

    dispatched_patches = []
    fake_req = _make_fake_http_request(client, patch_tracker=dispatched_patches)
    monkeypatch.setattr(simulate_driver, "_http_request", fake_req)

    rc = simulate_driver.run_simulation(
        order_id=order_id, delay=0.01, base_url="http://test"
    )
    assert rc == 0
    assert dispatched_patches == ["PICKED_UP", "DELIVERED"]

    tracking_res = client.get(f"/orders/{order_id}/tracking")
    assert tracking_res.status_code == 200
    assert tracking_res.json()["current_status"] == "DELIVERED"


def test_simulator_fails_gracefully_on_terminal_order(monkeypatch, client, capsys):
    """Places order and cancels it, runs simulation, asserts return code 1 and error message."""
    order = _create_order(client)
    order_id = order["id"]

    cancel_res = client.patch(f"/orders/{order_id}/status", json={"status": "CANCELLED"})
    assert cancel_res.status_code == 200

    fake_req = _make_fake_http_request(client)
    monkeypatch.setattr(simulate_driver, "_http_request", fake_req)

    rc = simulate_driver.run_simulation(
        order_id=order_id, delay=0.01, base_url="http://test"
    )
    assert rc == 1

    captured = capsys.readouterr()
    output = (captured.out + captured.err).lower()
    assert "terminal" in output or "cancelled" in output


def test_simulator_fails_gracefully_on_already_delivered_order(monkeypatch, client, capsys):
    """Places order, delivers it, runs simulation, asserts return code 1 and error message."""
    order = _create_order(client)
    order_id = order["id"]

    for st in ["PREPARING", "READY", "PICKED_UP", "DELIVERED"]:
        res = client.patch(f"/orders/{order_id}/status", json={"status": st})
        assert res.status_code == 200

    fake_req = _make_fake_http_request(client)
    monkeypatch.setattr(simulate_driver, "_http_request", fake_req)

    rc = simulate_driver.run_simulation(
        order_id=order_id, delay=0.01, base_url="http://test"
    )
    assert rc == 1

    captured = capsys.readouterr()
    output = (captured.out + captured.err).lower()
    assert "terminal" in output or "delivered" in output


def test_simulator_fails_on_nonexistent_order(monkeypatch, client):
    """Runs simulation with order_id=99999, asserts return code 1."""
    fake_req = _make_fake_http_request(client)
    monkeypatch.setattr(simulate_driver, "_http_request", fake_req)

    rc = simulate_driver.run_simulation(
        order_id=99999, delay=0.01, base_url="http://test"
    )
    assert rc == 1


def test_simulator_fails_when_patch_fails(monkeypatch, client, capsys):
    """Runs simulation where PATCH fails with HTTP error, asserts return code 1."""
    order = _create_order(client)
    order_id = order["id"]

    def failing_http_request(method: str, url: str, body: Optional[dict] = None) -> tuple[int, dict]:
        if method.upper() == "PATCH":
            return 500, {"detail": "Internal Server Error"}
        res = client.request(method=method, url=url, json_body=body)
        return res.status_code, res.json()

    monkeypatch.setattr(simulate_driver, "_http_request", failing_http_request)

    rc = simulate_driver.run_simulation(
        order_id=order_id, delay=0.01, base_url="http://test"
    )
    assert rc == 1
    captured = capsys.readouterr()
    assert "Failed to advance order" in captured.err


def test_simulator_cli_main(monkeypatch, client):
    """Tests CLI entrypoint main() parsing arguments and invoking simulation."""
    order = _create_order(client)
    order_id = order["id"]

    fake_req = _make_fake_http_request(client)
    monkeypatch.setattr(simulate_driver, "_http_request", fake_req)

    rc = simulate_driver.main([
        "--order-id", str(order_id),
        "--delay", "0.01",
        "--base-url", "http://test",
    ])
    assert rc == 0

    tracking_res = client.get(f"/orders/{order_id}/tracking")
    assert tracking_res.status_code == 200
    assert tracking_res.json()["current_status"] == "DELIVERED"


def test_http_request_helper_error_handling():
    """Tests standard urllib _http_request error handling on unreachable host."""
    status_code, data = simulate_driver._http_request(
        "GET", "http://127.0.0.1:59999/invalid-nonexistent-endpoint-test"
    )
    assert status_code == 0
    assert "detail" in data
