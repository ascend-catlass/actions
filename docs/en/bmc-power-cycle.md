# BMC power cycle

Uses the Python 3 standard library with no additional dependencies:

```console
python scripts/bmc_power_cycle.py <ip> <username> [password]
```

If omitted, the password comes from `BMC_PASSWORD` or an interactive prompt. Never store passwords in files or commits. Use `--status-only` to test login and query power without changing it. Use `--ca-cert <PEM file>` to trust the BMC certificate. HTTPS verification is enabled by default; explicitly pass `--insecure` only when accepting the risk of skipping certificate verification.

The script GETs `/itf/randomtag`, then POSTs form fields `encrypt_flag=0`, `username`, `password`, and `login_tag` to `/itf/session`. Only firmware with `encrypt_ctrl=0` is supported. It retains cookies and sends the returned `CSRFToken` in `X-CSRFTOKEN`.

POST `/itf/actions/power` accepts JSON `power_command`: 0 force off, 1 on, 2 force off then on, 3 hard reset, 5 soft shutdown. The default command is 2 and immediately interrupts host workloads; an already-off host receives 1 instead. Failed commands are never automatically replayed. After 20 seconds it polls GET `/itf/chassis-status`, for up to 180 seconds, to verify `power_status=1`. This does not verify OS or SSH readiness. Finally, DELETE `/itf/session` closes the session.
