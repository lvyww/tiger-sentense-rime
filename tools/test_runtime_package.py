"""Verify a runtime ZIP, then deploy its exact files in an isolated Rime directory."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--plugin", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    host_results = []
    with tempfile.TemporaryDirectory(prefix="tiger-rime-runtime-") as directory:
        root = Path(directory)
        user = root / "user"
        user.mkdir()
        with zipfile.ZipFile(args.archive) as archive:
            names = archive.namelist()
            assert names and len(names) == len(set(names)), "Duplicate/empty package"
            prefixes = {PurePosixPath(name).parts[0] for name in names}
            assert len(prefixes) == 1, "Package must have one root folder"
            prefix = next(iter(prefixes))
            checks = {}
            for line in archive.read(prefix + "/SHA256SUMS.txt").decode("utf-8").splitlines():
                digest, name = line.split("  ", 1)
                assert re.fullmatch(r"[0-9a-f]{64}", digest) and name not in checks
                checks[name] = digest
            relative_names = {name[len(prefix) + 1:] for name in names}
            assert relative_names == set(checks) | {"SHA256SUMS.txt"}, "Manifest coverage mismatch"
            for name in names:
                relative = PurePosixPath(name).relative_to(prefix)
                assert relative.parts and ".." not in relative.parts and not relative.is_absolute()
                assert relative.parts[0] not in {"tools", ".git", "tests", "validation"}
                destination = user.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                # Buffered extraction avoids platform copyfile/sendfile shortcuts.
                with archive.open(name) as source, destination.open("wb") as target:
                    for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
                        digest.update(chunk)
                        target.write(chunk)
                if str(relative) in checks:
                    assert digest.hexdigest() == checks[str(relative)], "Payload hash mismatch: " + str(relative)
        release = json.loads((user / "RELEASE.json").read_text())
        model = json.loads((user / "default-model.json").read_text())
        assert release["distribution"] == "deployable-runtime" and not release["separate_source_archive"]
        assert release["model"] == model and checks["models/sentence-fivegram-mobile.bin"] == model["sha256"]
        assert (user / "models/sentence-fivegram-mobile.bin").stat().st_size == model["bytes"]
        with (user / "models/sentence-fivegram-mobile.bin").open("rb") as stream:
            assert stream.read(8) == b"TCSKNM03"
        shared = root / "shared"
        shared.mkdir()
        (shared / "default.yaml").write_text(
            'config_version: "1.0"\nschema_list:\n  - schema: tiger_sentence\n'
            'menu:\n  page_size: 5\nrecognizer:\n  patterns: {}\n', encoding="utf-8")
        for mode in ("fresh", "reload"):
            completed = subprocess.run(
                [str(args.exe.resolve()), str(user), str(shared), str(args.plugin.resolve()),
                 release["schema_version"], mode], check=False, text=True, encoding="utf-8",
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
            print(completed.stdout, end="", flush=True)
            completed.check_returncode()
            rows = [json.loads(line) for line in completed.stdout.splitlines() if line.startswith("{")]
            assert rows and rows[-1]["status"] == "passed"
            host_results.append(rows[-1])
        for name, expected in checks.items():
            digest = hashlib.sha256()
            with (user / name).open("rb") as stream:
                for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                    digest.update(chunk)
            assert digest.hexdigest() == expected, "Deployment modified a packaged runtime file: " + name
        result = {
            "status": "passed", "source_commit": release["source_commit"],
            "schema_version": release["schema_version"], "payload_files_verified": len(checks),
            "archive_entries": len(names), "model": model, "host_results": host_results,
            "runtime_files_modified_for_probe": False, "installed_user_directory_modified": False,
            "tools_tests_git_history_included": False,
        }
        args.result.parent.mkdir(parents=True, exist_ok=True)
        args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
