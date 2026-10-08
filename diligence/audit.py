"""Append-only run log. Each line carries the hash of the line before it, so an
edited or deleted entry shows up when the chain is checked."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def append(log_path, event):
    log_path = Path(log_path)
    prev = "0" * 64
    if log_path.exists():
        lines = log_path.read_text().strip().splitlines()
        if lines:
            prev = json.loads(lines[-1])["hash"]
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "prev": prev, **event}
    entry["hash"] = hashlib.sha256((prev + json.dumps(entry, sort_keys=True)).encode()).hexdigest()
    with open(log_path, "a") as fh:
        fh.write(json.dumps(entry) + "\n")


def verify(log_path):
    prev = "0" * 64
    for line in Path(log_path).read_text().strip().splitlines():
        e = json.loads(line)
        h = e.pop("hash")
        if e["prev"] != prev or hashlib.sha256((prev + json.dumps(e, sort_keys=True)).encode()).hexdigest() != h:
            return False
        prev = h
    return True
