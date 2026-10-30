from datetime import datetime, timedelta, timezone
from typing import Optional, Union
from app.schemas.order import OrderStatus

# Municipal delivery transit time is fixed at 15 minutes
TRANSIT_TIME_MINUTES = 15


def calculate_eta(
    status: Union[OrderStatus, str],
    transition_time: Union[datetime, str],
    avg_prep_minutes: int,
) -> Optional[str]:
    """Calculate deterministic ETA based on order status, transition timestamp, and prep time.

    Formulas:
        - PLACED / PREPARING: t + avg_prep_minutes + 15 min transit
        - READY / PICKED_UP: t + 15 min transit
        - DELIVERED: t
        - CANCELLED: None

    Args:
        status: The target or current OrderStatus (enum or string).
        transition_time: The transition datetime (or ISO formatted string).
        avg_prep_minutes: Average preparation time of the restaurant in minutes.

    Returns:
        ISO 8601 formatted UTC timestamp string, or None if cancelled.
    """
    if isinstance(status, str):
        try:
            status_enum = OrderStatus(status.upper())
        except ValueError:
            raise ValueError(f"Invalid order status: {status}")
    else:
        status_enum = status

    if status_enum == OrderStatus.CANCELLED:
        return None

    if isinstance(transition_time, str):
        transition_dt = datetime.fromisoformat(transition_time.replace("Z", "+00:00"))
    else:
        transition_dt = transition_time

    if transition_dt.tzinfo is None:
        transition_dt = transition_dt.replace(tzinfo=timezone.utc)
    else:
        transition_dt = transition_dt.astimezone(timezone.utc)

    prep_minutes = max(0, int(avg_prep_minutes))

    if status_enum in (OrderStatus.PLACED, OrderStatus.PREPARING):
        eta = transition_dt + timedelta(minutes=prep_minutes + TRANSIT_TIME_MINUTES)
        return eta.isoformat()
    elif status_enum in (OrderStatus.READY, OrderStatus.PICKED_UP):
        eta = transition_dt + timedelta(minutes=TRANSIT_TIME_MINUTES)
        return eta.isoformat()
    elif status_enum == OrderStatus.DELIVERED:
        return transition_dt.isoformat()

    return None
