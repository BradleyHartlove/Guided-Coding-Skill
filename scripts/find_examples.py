#!/usr/bin/env python3
"""List sibling repos that can serve as examples for guided-coding.

Reads the examples root from, in order:
  1. --root argument
  2. GUIDED_CODING_EXAMPLES_ROOT environment variable
  3. .guided-coding.json in the repo given by --repo (default: current directory)
  4. ~/.claude/guided-coding.json (key: examples_root)

Prints one line per candidate repo: name, detected languages, whether it has
agent instructions (AGENTS.md / CLAUDE.md), and last commit age. Pass
--lang go (or rust, python, ts) to keep only repos in that language, and
--exclude <name> to drop the repo you're currently working in.

Usage:
  python3 find_examples.py --repo /path/to/current/repo [--lang LANG] [--json]
  python3 find_examples.py --root DIR [--lang LANG] [--exclude NAME] [--json]

--repo also excludes that repo from the results automatically.
"""
import argparse
import json
import os
import subprocess
import sys

MARKERS = {
    "go": ["go.mod"],
    "rust": ["Cargo.toml"],
    "python": ["pyproject.toml", "setup.py", "requirements.txt"],
    "ts": ["package.json", "tsconfig.json"],
    "terraform": ["main.tf"],
    "helm": ["charts"],
}
INSTRUCTION_FILES = ["AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md"]


def resolve_root(cli_root, repo_dir):
    if cli_root:
        return os.path.expanduser(cli_root), "--root"
    env = os.environ.get("GUIDED_CODING_EXAMPLES_ROOT")
    if env:
        return os.path.expanduser(env), "GUIDED_CODING_EXAMPLES_ROOT"
    for path, label in [
        (os.path.join(repo_dir, ".guided-coding.json"), os.path.join(repo_dir, ".guided-coding.json")),
        (os.path.expanduser("~/.claude/guided-coding.json"), "~/.claude/guided-coding.json"),
    ]:
        if os.path.isfile(path):
            try:
                root = json.load(open(path)).get("examples_root")
            except (json.JSONDecodeError, OSError):
                root = None
            if root:
                return os.path.expanduser(root), label
    return None, None


def detect_langs(repo):
    langs = []
    for lang, files in MARKERS.items():
        for f in files:
            if os.path.exists(os.path.join(repo, f)):
                langs.append(lang)
                break
    return langs


def last_commit_age(repo):
    try:
        out = subprocess.run(
            ["git", "-C", repo, "log", "-1", "--format=%cr"],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or "no commits"
    except Exception:
        return "not a git repo"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root")
    ap.add_argument("--repo", help="the repo being worked on; its .guided-coding.json is checked and it is excluded from results")
    ap.add_argument("--lang")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo_dir = os.path.abspath(os.path.expanduser(args.repo)) if args.repo else os.getcwd()
    if args.repo:
        args.exclude.append(os.path.basename(repo_dir.rstrip("/")))
    root, source = resolve_root(args.root, repo_dir)
    if not root:
        print(
            "No examples root configured. Set one with:\n"
            '  echo \'{"examples_root": "/path/to/your/repos"}\' > ~/.claude/guided-coding.json\n'
            "or export GUIDED_CODING_EXAMPLES_ROOT=/path/to/your/repos",
            file=sys.stderr,
        )
        sys.exit(2)
    if not os.path.isdir(root):
        print(f"Examples root from {source} does not exist: {root}", file=sys.stderr)
        sys.exit(2)

    results = []
    for name in sorted(os.listdir(root)):
        repo = os.path.join(root, name)
        if not os.path.isdir(repo) or name.startswith(".") or name in args.exclude:
            continue
        langs = detect_langs(repo)
        if not langs:
            continue
        if args.lang and args.lang not in langs:
            continue
        instructions = [f for f in INSTRUCTION_FILES if os.path.exists(os.path.join(repo, f))]
        results.append({
            "name": name,
            "path": repo,
            "languages": langs,
            "instructions": instructions,
            "last_commit": last_commit_age(repo),
        })

    if args.json:
        print(json.dumps({"root": root, "source": source, "repos": results}, indent=2))
        return
    print(f"examples root: {root}  (from {source})")
    if not results:
        print("no candidate repos found")
        return
    for r in results:
        instr = ", ".join(r["instructions"]) if r["instructions"] else "none"
        print(f"- {r['name']}: {'/'.join(r['languages'])}; instructions: {instr}; last commit {r['last_commit']}")
        print(f"    {r['path']}")


if __name__ == "__main__":
    main()
