# FleetLuma monitoring agent

Planned: Python 3, psutil, metrics collection on Linux/Windows and authenticated outgoing reporting. Work tracked by FL-7. Currently no implementation.

Configuration: duplicate `.env.example` locally as `.env` (ignored by git), provision a unique token per host outside version control, and use an HTTP(S) coordinator URL reachable from the host.
