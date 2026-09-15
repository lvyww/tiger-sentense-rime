#!/usr/bin/env python3
"""Build a compact TCSLEX01 lexical-prior Bloom filter.

The source is a Rime YAML dictionary whose data section has named ``text`` and
``weight`` columns.  Only reachable 2--4 character entries are considered;
the highest-weight entries are retained.  The runtime representation contains
no word strings or weights and is intended for bounded Top-K reranking.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Iterable

MAGIC = b"TCSLEX01"
VERSION = 1
MODULUS = 4_294_967_291


def parse_codes(path: Path) -> set[str]:
    characters: set[str] = set()
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if fields and len(fields[0]) == 1:
            characters.add(fields[0])
    return characters


def dictionary_columns(path: Path) -> tuple[list[str], list[str]]:
    columns: list[str] = []
    data: list[str] = []
    in_columns = False
    in_data = False
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if line == "...":
            in_data = True
            in_columns = False
            continue
        if in_data:
            if line and not line.startswith("#"):
                data.append(raw)
            continue
        if line == "columns:":
            in_columns = True
            continue
        if in_columns:
            if line.startswith("-"):
                columns.append(line[1:].strip())
            elif line and not line.startswith("#"):
                in_columns = False
    if "text" not in columns or "weight" not in columns:
        raise ValueError(f"{path} must declare text and weight columns")
    return columns, data


def ranked_words(path: Path, reachable: set[str], minimum: int, maximum: int) -> list[tuple[str, float]]:
    columns, rows = dictionary_columns(path)
    text_index = columns.index("text")
    weight_index = columns.index("weight")
    weights: dict[str, float] = {}
    for raw in rows:
        fields = raw.split("\t")
        if max(text_index, weight_index) >= len(fields):
            continue
        word = fields[text_index].strip()
        if not minimum <= len(word) <= maximum or any(ch not in reachable for ch in word):
            continue
        try:
            weight = float(fields[weight_index])
        except ValueError:
            continue
        if not math.isfinite(weight) or weight < 0:
            continue
        weights[word] = max(weight, weights.get(word, -1.0))
    return sorted(weights.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))


def hashes(text: str) -> tuple[int, int]:
    first, second = 2_166_136_261, 16_777_619
    for byte in text.encode("utf-8"):
        first = (first * 131 + byte + 17) % MODULUS
        second = (second * 137 + byte + 53) % MODULUS
    return first, second or 1


def build_filter(words: Iterable[str], bit_count: int, hash_count: int) -> bytes:
    payload = bytearray(bit_count // 8)
    for word in words:
        first, second = hashes(word)
        for index in range(hash_count):
            bit = (first + index * second + index * index * 97) % bit_count
            payload[bit // 8] |= 1 << (bit % 8)
    return bytes(payload)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--source-repository")
    parser.add_argument("--source-revision")
    parser.add_argument("--source-license", default="CC-BY-4.0")
    parser.add_argument("--codes", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--limit", type=int, default=50_000)
    parser.add_argument("--bits-per-entry", type=int, default=24)
    parser.add_argument("--hashes", type=int, default=10)
    parser.add_argument("--min-length", type=int, default=2)
    parser.add_argument("--max-length", type=int, default=4)
    args = parser.parse_args()

    if args.limit < 1 or args.bits_per_entry < 8 or not 1 <= args.hashes <= 32:
        parser.error("limit, bits-per-entry, or hashes is outside the supported range")
    if not 2 <= args.min_length <= args.max_length <= 16:
        parser.error("word lengths must satisfy 2 <= min <= max <= 16")

    reachable = parse_codes(args.codes)
    ranked = ranked_words(
        args.source, reachable, args.min_length, args.max_length
    )
    selected = ranked[: args.limit]
    if not selected:
        raise SystemExit("no eligible lexical entries")
    # Byte-align the payload while retaining the requested lower bound.
    bit_count = ((len(selected) * args.bits_per_entry + 7) // 8) * 8
    payload = build_filter((word for word, _ in selected), bit_count, args.hashes)
    header = MAGIC + struct.pack(
        "<6I",
        VERSION,
        len(selected),
        bit_count,
        args.hashes,
        args.min_length,
        args.max_length,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(header + payload)

    false_positive = (1 - math.exp(-args.hashes * len(selected) / bit_count)) ** args.hashes
    manifest = {
        "format": "TCSLEX01",
        "source_file": args.source.name,
        "source_repository": args.source_repository,
        "source_revision": args.source_revision,
        "source_license": args.source_license,
        "source_sha256": sha256(args.source),
        "codes_sha256": sha256(args.codes),
        "entries": len(selected),
        "eligible_entries": len(ranked),
        "minimum_length": args.min_length,
        "maximum_length": args.max_length,
        "bits": bit_count,
        "hashes": args.hashes,
        "estimated_false_positive_rate": false_positive,
        "output_bytes": len(header) + len(payload),
        "output_sha256": sha256(args.output),
        "selection": "highest source weight, then longer word, then Unicode order",
    }
    if args.manifest:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
