"""Portable approval polling used by native Windows and Linux services.

No operating-system socket or GUI dependencies belong here.
"""
from __future__ import annotations

import logging
import threading

from .pairing_client import PairingRejected
from .service_runtime import EnrollmentController

LOG = logging.getLogger("fleetluma.agent.pairing_poller")


def automatic_poller(controller: EnrollmentController,
                     stop_event: threading.Event, interval: float = 1.0) -> None:
    """Poll only pending device enrollment; never expose device-code secret."""
    while not stop_event.is_set():
        try:
            if controller.status().status == "waiting":
                controller.poll_once()
        except (PairingRejected, OSError, RuntimeError, ValueError) as exc:
            LOG.warning("Pairing poll failed (%s)", type(exc).__name__)
        stop_event.wait(interval)
