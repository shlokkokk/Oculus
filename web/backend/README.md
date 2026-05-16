# Oculus Web Backend

This backend is intentionally thin. It validates browser requests, starts the existing `oculus.py` CLI as a subprocess, streams stdout over server-sent events, and exposes generated report artifacts from `output-<domain>/`.

The Python CLI remains the source of truth. Add future modules in `web/shared/modules.json`, then wire any new mode behavior in `oculus.py` when the CLI supports it.
