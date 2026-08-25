import os, signal

me = os.getpid()
killed = 0
for pid in os.listdir("/proc"):
    if not pid.isdigit() or int(pid) == me:
        continue
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            cmd = f.read().decode(errors="ignore")
    except Exception:
        continue
    # только python-процессы orchestrator, не bash
    if "orchestrator.py" in cmd and "python" in cmd and "_loop" in cmd:
        try:
            os.kill(int(pid), signal.SIGKILL)
            killed += 1
            print("killed", pid)
        except Exception:
            pass
print(f"done ({killed})")
