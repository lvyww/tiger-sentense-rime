"""Create one deployable Rime runtime archive from a clean, committed tree.

The large production model is supplied separately and checked against
default-model.json. No repository source archive, developer tools or Git data
are included. Python zipfile uses buffered I/O; never copy via sendfile.
"""
import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILES = (
    "tiger_sentence.schema.yaml", "tiger_sentence_ascii.schema.yaml",
    "tiger_sentence.codes.txt", "tiger_sentence.char_ranks.txt",
    "tiger_sentence.full_code_whitelist.txt", "tiger_sentence.supplement.txt",
    "symbols.yaml", "rime.lua", "default.custom.yaml", "default-model.json",
    "models/tiger_sentence.lexical.bin", "LICENSE",
    "docs/LEXICAL_PRIOR_ATTRIBUTION.md", "docs/LEXICAL_PRIOR_MANIFEST.json",
)
MODEL_ENTRY = "models/sentence-fivegram-mobile.bin"


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def stream_hash(stream):
    result = hashlib.sha256()
    for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
        result.update(chunk)
    return result.hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    assert not git("status", "--porcelain"), "Release source must be clean"
    commit, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    version = re.search(r'^\s+version:\s*"([^"]+)"', (ROOT / "tiger_sentence.schema.yaml").read_text(), re.M)[1]
    assert re.fullmatch(r"[0-9.]+", version), "Unsafe version"
    model = json.loads((ROOT / "default-model.json").read_text())
    assert args.model.is_file() and args.model.stat().st_size == model["bytes"], "Wrong model size"
    assert sha256(args.model) == model["sha256"], "Wrong production model hash"
    with args.model.open("rb") as stream:
        assert stream.read(8) == b"TCSKNM03", "Wrong model format"
    tracked = set(git("ls-files", "-z").split("\0"))
    names = list(RUNTIME_FILES) + sorted(name for name in tracked if name.startswith("lua/") and name.endswith(".lua"))
    assert len(names) == len(set(names)) and len([name for name in names if name.startswith("lua/")]) >= 8
    assert all(name in tracked and (ROOT / name).is_file() for name in names)
    entries = {name: ROOT / name for name in names}
    entries[MODEL_ENTRY] = args.model.resolve()
    entries["安装与更新说明.txt"] = ROOT / "docs/RUNTIME_INSTALL.txt"
    source_files = {
        name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for name, path in sorted(entries.items())
    }
    prior = json.loads((ROOT / "docs/LEXICAL_PRIOR_MANIFEST.json").read_text())
    assert source_files["models/tiger_sentence.lexical.bin"]["sha256"] == prior["output_sha256"]
    assert source_files["tiger_sentence.codes.txt"]["sha256"] == prior["codes_sha256"]
    source_learning = (ROOT / "lua/tiger_sentence_learning.lua").read_text()
    source_main = (ROOT / "lua/tiger_sentence.lua").read_text()
    assert "function M.selection_events(" in source_learning
    assert "function M.is_legacy_mode(" in source_learning
    assert "function M.fusion_event(" not in source_learning
    assert "function M.exact_correction_event(" not in source_learning
    assert "function learning.apply_source_ordering(" in source_main
    assert "apply_exact_correction_ordering(" not in source_main
    manifest = {
        "project": "tiger-sentense-rime",
        "distribution": "deployable-runtime",
        "schema_id": "tiger_sentence",
        "schema_version": version,
        "source_repository": "https://github.com/lvyww/tiger-sentense-rime",
        "source_branch": git("branch", "--show-current"),
        "source_commit": commit,
        "source_tree": tree,
        "separate_source_archive": False,
        "includes_production_model": True,
        "model": model,
        "production_defaults": {
            "auto_select_min_code_length": 3, "auto_select_minimum": 0, "auto_select_maximum": 128,
            "high_freq_limit": 1500, "canonical_code_reward": 0,
            "whole_input_single_character_reward": 5, "correction_default": "off",
            "correction_penalties": {"weak": 8, "medium": 6, "strong": 4},
        },
        "learning": {
            "ordinary_reusable_fragments": True,
            "standalone_two_characters_learn_whole": True,
            "direct_table_order_preserved": True,
            "ignored_modes": ["fusion-v1|", "exact-correction-v1|"],
            "legacy_rows_migrated": False,
            "legacy_rows_deleted": False,
        },
        "files": source_files,
    }
    additions = {"RELEASE.json": encoded(manifest)}
    checks = {name: value["sha256"] for name, value in source_files.items()}
    checks["RELEASE.json"] = hashlib.sha256(additions["RELEASE.json"]).hexdigest()
    additions["SHA256SUMS.txt"] = "".join(checks[name] + "  " + name + "\n" for name in sorted(checks)).encode("utf-8")
    args.output_directory.mkdir(parents=True, exist_ok=True)
    prefix = "虎整句Rime-" + version
    destination = args.output_directory / (prefix + "-完整包.zip")
    assert not destination.exists(), "Do not overwrite an existing release"
    print("Writing deployable runtime archive", flush=True)
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for name, path in sorted(entries.items()):
            archive.write(path, prefix + "/" + name)
        for name, data in sorted(additions.items()):
            archive.writestr(prefix + "/" + name, data)
    print("Verifying every archived file and production model", flush=True)
    with zipfile.ZipFile(destination) as archive:
        assert archive.testzip() is None, "Archive CRC mismatch"
        assert len(archive.namelist()) == len(entries) + len(additions)
        assert all(name.startswith(prefix + "/") and "/tools/" not in name and "/.git" not in name for name in archive.namelist())
        for name, expected in checks.items():
            with archive.open(prefix + "/" + name) as stream:
                assert stream_hash(stream) == expected, "Archived file mismatch: " + name
        assert archive.read(prefix + "/SHA256SUMS.txt") == additions["SHA256SUMS.txt"]
    result = {
        "project": "rime", "version": version, "source_commit": commit, "source_tree": tree,
        "path": str(destination.resolve()), "file": destination.name, "bytes": destination.stat().st_size,
        "sha256": sha256(destination), "zip_prefix": prefix, "zip_entries": len(entries) + len(additions),
        "payload_files_verified": len(checks), "model": model, "runtime_source_files": source_files,
        "basic_deployment": "pending",
    }
    destination.with_suffix(destination.suffix + ".sha256").write_text(result["sha256"] + "  " + destination.name + "\n", encoding="utf-8")
    (args.output_directory / "rime-runtime-package.json").write_bytes(encoded(result))
    assert not git("status", "--porcelain"), "Packaging changed the source tree"
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
