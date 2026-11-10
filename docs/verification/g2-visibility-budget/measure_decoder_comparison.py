"""Compare existing zlib decoders on a previously generated durable fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sqlite3
import statistics
import sys
import time
import zlib
from pathlib import Path

from zlib_ng import zlib_ng

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from app.gameplay.event_store import _DURABLE_JSON_PREFIX


def outcome(codec, body):
    try:
        return ("ok", codec.decompress(body))
    except Exception as exc:
        return ("error", str(exc))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--warmups", type=int, default=10)
    args = parser.parse_args()
    if args.samples < 1 or args.warmups < 1:
        parser.error("samples and warmups must be positive")
    with sqlite3.connect(f"{args.database.resolve().as_uri()}?mode=ro", uri=True) as db:
        bodies = [row[0] for row in db.execute("SELECT full_value FROM events ORDER BY global_sequence")]
    if not bodies or any(type(body) is not bytes or not body.startswith(_DURABLE_JSON_PREFIX) for body in bodies):
        raise ValueError("fixture_requires_compressed_event_bodies")
    bodies = [body[len(_DURABLE_JSON_PREFIX):] for body in bodies]
    reference = [zlib.decompress(body) for body in bodies]
    if [zlib_ng.decompress(body) for body in bodies] != reference:
        raise ValueError("decoder_output_mismatch")
    body = bodies[0]
    cases = {"truncated": body[:-1], "checksum": body[:-1] + bytes([body[-1] ^ 1]),
             "trailing": body + b"x"}
    outcomes = {}
    for name, value in cases.items():
        old, candidate = outcome(zlib, value), outcome(zlib_ng, value)
        if old != candidate:
            raise ValueError(f"decoder_outcome_mismatch:{name}")
        outcomes[name] = old[0]
    codecs = {"stdlib": zlib, "native": zlib_ng}
    timings = {name: [] for name in codecs}
    for iteration in range(args.samples + args.warmups):
        order = ("stdlib", "native") if iteration % 2 == 0 else ("native", "stdlib")
        for name in order:
            start = time.perf_counter_ns()
            decoded = [codecs[name].decompress(value) for value in bodies]
            elapsed = (time.perf_counter_ns() - start) / 1_000_000
            if decoded != reference:
                raise ValueError("decoder_output_mismatch_during_measurement")
            if iteration >= args.warmups:
                timings[name].append(elapsed)
    args.output.write_text(json.dumps({
        "measurement": "compressed-fixture-decoding-only-not-read-as",
        "database": str(args.database.resolve()), "event_count": len(bodies),
        "fixture_sha256": hashlib.sha256(b"".join(bodies)).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": sys.version, "platform": platform.platform(),
        "samples": args.samples, "warmups": args.warmups,
        "ordering": "alternating", "corrupt_outcomes": outcomes,
        "timings_ms": timings,
        "median_ms": {name: statistics.median(values) for name, values in timings.items()},
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
