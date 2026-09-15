"""Compare old/new decoder snapshots in isolated processes, using one probe.

python tools/compare_revisions.py --baseline /path/to/old/tree --lua lua5.4
python tools/compare_revisions.py --baseline /path/to/old/tree --fixture --lua lua5.4
python tools/compare_revisions.py --baseline /path/to/old/tree --model /path/to/model.bin --require-model
python tools/compare_revisions.py --baseline /path/to/old/tree --fixture --legacy-ranking

No model silently falls back. This is behavior equivalence, not a labeled-text
accuracy benchmark or desktop/mobile acceptance. Intentional long-code/selector
fixes are covered separately by test_review_regressions.lua.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, default=ROOT)
    parser.add_argument("--lua", default="lua")
    models = parser.add_mutually_exclusive_group()
    models.add_argument("--model", type=Path)
    models.add_argument("--fixture", action="store_true")
    parser.add_argument("--require-model", action="store_true")
    parser.add_argument("--cases", type=int, default=20)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--memory-profile", choices=("balanced", "compact"), default="balanced")
    parser.add_argument("--trim-every", type=int, default=0, help="Exercise memory-pressure hook between snapshot generations")
    parser.add_argument("--legacy-ranking", action="store_true",
                        help="Disable compact ranking priors when a source exposes the test hook")
    args = parser.parse_args()
    lua = shutil.which(args.lua)
    if not lua:
        parser.error("Lua interpreter not found")
    if args.require_model and not args.model:
        parser.error("--require-model requires an explicit --model (a synthetic fixture is not a production model)")
    if args.trim_every < 0:
        parser.error("--trim-every must be nonnegative")
    if args.cases < 0 or args.cases > 1000:
        parser.error("--cases must be between 0 and 1000")
    baseline, candidate = args.baseline.resolve(), args.candidate.resolve()
    for tree in (baseline, candidate):
        if not (tree / "lua/tiger_sentence.lua").is_file():
            parser.error(f"Not a source tree: {tree}")
    if args.model and not args.model.is_file():
        parser.error(f"Model is not a readable file: {args.model}")
    probe = ROOT / "tools/snapshot_decoder.lua"
    with tempfile.TemporaryDirectory(prefix="tiger-equivalence-") as tmp:
        work = Path(tmp)
        model = args.model.resolve() if args.model else None
        if args.fixture:
            model = work / "fixture.bin"
            generator = work / "generate.lua"
            generator.write_text("local make=dofile(arg[1]); make(arg[2])\n", encoding="utf-8")
            subprocess.run([lua, str(generator), str(ROOT / "tools/model_fixture.lua"), str(model)], check=True, timeout=30)
        if model:
            with model.open("rb") as stream:
                if stream.read(8) != b"TCSKNM02":
                    parser.error("Only an explicit TCSKNM02 model is accepted")
        outputs, stats = [], []
        for label, tree in (("baseline", baseline), ("candidate", candidate)):
            data = work / label
            data.mkdir()
            for pattern in ("*.txt", "*.yaml", "tiger_sentence.lexical.bin"):
                for source in tree.glob(pattern):
                    shutil.copy2(source, data / source.name)
            if model:
                (data / "models").mkdir()
                destination = data / "models/sentence-ngram-mobile.bin"
                try:
                    destination.symlink_to(model)
                except OSError:
                    shutil.copy2(model, destination)
            output = work / (label + ".snapshot")
            with output.open("wb") as stream:
                result = subprocess.run([lua, str(probe), str(tree), str(data),
                                         "mobile" if model else "none", str(args.cases),
                                         args.memory_profile, str(args.trim_every),
                                         "legacy-ranking" if args.legacy_ranking else "current-ranking"],
                                        stdout=stream, stderr=subprocess.PIPE, timeout=600)
            if result.returncode:
                raise RuntimeError(f"{label} probe failed:\n{result.stderr.decode('utf-8', errors='replace')}")
            outputs.append(output)
            stats.append(json.loads(result.stderr.decode("utf-8").strip().splitlines()[-1]))
        mismatch = None
        with outputs[0].open("rb") as old, outputs[1].open("rb") as new:
            line = 0
            while True:
                a, b = old.readline(), new.readline()
                if not a and not b:
                    break
                line += 1
                if a != b:
                    offset = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                    mismatch = {"line": line, "byte_offset": offset,
                                "baseline": a[max(0, offset-160):offset+160].decode("utf-8", errors="replace"),
                                "candidate": b[max(0, offset-160):offset+160].decode("utf-8", errors="replace")}
                    break
        report = {"status": "failed" if mismatch else "passed", "probe_sha256": digest(probe),
                  "baseline_module_sha256": digest(baseline / "lua/tiger_sentence.lua"),
                  "candidate_module_sha256": digest(candidate / "lua/tiger_sentence.lua"),
                  "model_source": "synthetic" if args.fixture else "explicit-file" if model else "none",
                  "model_sha256": digest(model) if model else None,
                  "random_cases": args.cases, "memory_profile": args.memory_profile,
                  "trim_every": args.trim_every, "legacy_ranking": args.legacy_ranking,
                  "baseline": stats[0], "candidate": stats[1],
                  "snapshot_sha256": [digest(p) for p in outputs], "first_mismatch": mismatch,
                  "source_manifests": {label: {str(p.relative_to(tree)): digest(p) for p in sorted(
                      list((tree / "lua").glob("*.lua")) +
                      list(tree.glob("tiger_sentence.lexical.bin")))}
                                       for label, tree in (("baseline", baseline), ("candidate", candidate))}}
        text = json.dumps(report, ensure_ascii=False, indent=2)
        print(text)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(text + "\n", encoding="utf-8")
        if mismatch:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
