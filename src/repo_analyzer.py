import io
import asyncio
import os
import json
import zipfile
import tempfile
import hashlib
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from typing import List, Dict, Any, Tuple

from .agent import CodeReviewAgent
from .config import config


def _parse_github_repo(repo_url: str) -> Tuple[str, str, str | None, str | None]:
    """Extract owner, repo, optional branch, and optional subpath from a GitHub URL.
    Supports URLs like:
      - https://github.com/owner/repo
      - https://github.com/owner/repo/
      - https://github.com/owner/repo.git
      - https://github.com/owner/repo/tree/<branch>/<subpath>
    Returns: (owner, repo, branch_or_None, subpath_or_None)
    """
    parsed = urlparse(repo_url)
    if parsed.netloc.lower() != "github.com":
        raise ValueError("Only github.com URLs are supported")
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repository URL. Expected format: https://github.com/<owner>/<repo>")
    owner, repo = parts[0], parts[1]
    if repo.endswith('.git'):
        repo = repo[:-4]
    branch = None
    subpath = None
    if len(parts) >= 4 and parts[2] == 'tree':
        branch = parts[3]
        if len(parts) > 4:
            subpath = "/".join(parts[4:])
    return owner, repo, branch, subpath


def _download_repo_zip(owner: str, repo: str, preferred_branch: str | None = None) -> bytes:
    """Download repo zip by trying preferred branch if provided, then fallbacks.
    Uses codeload to avoid HTML.
    """
    branches = []
    if preferred_branch:
        branches.append(preferred_branch)
    # Default fallbacks
    for br in ["main", "master"]:
        if br not in branches:
            branches.append(br)
    last_err: Exception | None = None
    for br in branches:
        url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{br}"
        try:
            req = Request(url, headers={"User-Agent": "Agentic-Code-Reviewer/1.0"})
            with urlopen(req, timeout=30) as resp:
                if resp.status == 200:
                    return resp.read()
        except Exception as e:
            last_err = e
            continue
    raise ValueError(f"Failed to download repository zip for {owner}/{repo}. Last error: {last_err}")


def _extract_zip_to_temp(zip_bytes: bytes) -> str:
    """Extract a zip into a temporary directory and return the root path."""
    tmpdir = tempfile.mkdtemp(prefix="repo_analyze_")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        zf.extractall(tmpdir)
    # The zip typically contains a single root folder: repo-branch/
    # Find the first directory in tmpdir
    entries = [os.path.join(tmpdir, d) for d in os.listdir(tmpdir)]
    dirs = [p for p in entries if os.path.isdir(p)]
    return dirs[0] if dirs else tmpdir


def _summarize_structure(root: str) -> Dict[str, Any]:
    by_dir: Dict[str, Dict[str, int]] = {}
    total_files = 0
    ext_counts: Dict[str, int] = {}

    for dirpath, _, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root)
        rel = "." if rel == "." else rel
        if rel not in by_dir:
            by_dir[rel] = {}
        for fn in filenames:
            total_files += 1
            ext = os.path.splitext(fn)[1].lower() or "<noext>"
            by_dir[rel][ext] = by_dir[rel].get(ext, 0) + 1
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

    # Build a simple tree-like string for top levels (depth 2)
    lines: List[str] = []
    for entry in sorted(os.listdir(root)):
        p = os.path.join(root, entry)
        if os.path.isdir(p):
            lines.append(f"/{entry}/")
            try:
                for sub in sorted(os.listdir(p))[:20]:
                    lines.append(f"  - {sub}/" if os.path.isdir(os.path.join(p, sub)) else f"  - {sub}")
            except Exception:
                pass
        else:
            lines.append(entry)

    return {
        "root": root,
        "total_files": total_files,
        "by_directory_extensions": by_dir,
        "extension_counts": dict(sorted(ext_counts.items(), key=lambda x: (-x[1], x[0]))),
        "top_level_tree": "\n".join(lines)
    }


def _read_notebook_code(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            nb = json.load(f)
        cells = nb.get("cells", [])
        code_parts: List[str] = []
        for c in cells:
            if c.get("cell_type") == "code":
                src = c.get("source", [])
                if isinstance(src, list):
                    code_parts.append("".join(src))
                elif isinstance(src, str):
                    code_parts.append(src)
        return "\n\n".join(code_parts)
    except Exception:
        return ""


def _select_files(root: str, include_exts: List[str], max_files: int) -> List[str]:
    selected: List[str] = []
    inc = set(e.lower() for e in include_exts)
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in inc:
                selected.append(os.path.join(dirpath, fn))
                if len(selected) >= max_files:
                    return selected
    return selected


def analyze_repository(repo_url: str, include_extensions: List[str] | None = None, max_files: int | None = None, override_branch: str | None = None, override_subdir: str | None = None) -> Dict[str, Any]:
    """Download a public GitHub repo, summarize structure, and review selected files.
    Returns a JSON-serializable dict.
    """
    include_extensions = include_extensions or getattr(config, "repo_allowed_extensions", [".py", ".ipynb"])
    max_files = max_files or getattr(config, "max_files_per_repo", 20)

    owner, repo, url_branch, url_subpath = _parse_github_repo(repo_url)
    branch = override_branch or url_branch
    subdir = override_subdir or url_subpath
    zip_bytes = _download_repo_zip(owner, repo, preferred_branch=branch)
    root = _extract_zip_to_temp(zip_bytes)

    # If a subdir is provided (via URL or override), narrow root to that folder
    if subdir:
        candidate = os.path.join(root, subdir)
        if not os.path.isdir(candidate):
            raise ValueError(f"Subdirectory '{subdir}' not found in the repository archive")
        root = candidate

    structure = _summarize_structure(root)

    files = _select_files(root, include_extensions, max_files)

    agent = CodeReviewAgent()
    file_results: List[Dict[str, Any]] = []

    size_limit = config.max_file_size_mb * 1024 * 1024

    for path in files:
        ext = os.path.splitext(path)[1].lower().lstrip('.') or 'txt'
        try:
            if path.lower().endswith('.ipynb'):
                code = _read_notebook_code(path)
                passed_ext = 'py'  # treat notebooks as Python for analysis
            else:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    code = f.read()
                passed_ext = ext

            if not code.strip():
                file_results.append({
                    "path": os.path.relpath(path, root),
                    "status": "skipped",
                    "reason": "empty or unreadable file"
                })
                continue

            if len(code.encode('utf-8')) > size_limit:
                file_results.append({
                    "path": os.path.relpath(path, root),
                    "status": "skipped",
                    "reason": f"file exceeds size limit {config.max_file_size_mb}MB"
                })
                continue

            # Run review synchronously via asyncio bridge per file
            result = asyncio.run(agent.review_code(code, passed_ext))
            file_results.append({
                "path": os.path.relpath(path, root),
                "status": "reviewed",
                "result": result
            })
        except Exception as e:
            file_results.append({
                "path": os.path.relpath(path, root),
                "status": "error",
                "error": str(e)
            })

    return {
        "status": "success",
        "repository": f"{owner}/{repo}",
        "branch": branch or "(auto)",
        "subdirectory": subdir or "",
        "structure_summary": structure,
        "selected_extensions": include_extensions,
        "files_analyzed": len([r for r in file_results if r.get("status") == "reviewed"]),
        "files_considered": len(files),
        "results": file_results
    }


def build_markdown_report(analysis: Dict[str, Any]) -> str:
    """Convert analyze_repository() output into a Markdown report string."""
    if not isinstance(analysis, dict) or analysis.get('status') != 'success':
        return "# Code Review Report\n\nNo valid analysis data provided."

    repo = analysis.get('repository', '')
    branch = analysis.get('branch', '')
    subdir = analysis.get('subdirectory', '')
    struct = analysis.get('structure_summary', {}) or {}
    ext_counts = struct.get('extension_counts', {}) or {}
    top_tree = struct.get('top_level_tree', '') or ''

    lines: List[str] = []
    lines.append(f"# Code Review Report — {repo}")
    lines.append("")
    lines.append("## Repository Info")
    lines.append("")
    lines.append(f"- **Repository**: `{repo}`")
    lines.append(f"- **Branch**: `{branch}`")
    lines.append(f"- **Subdirectory**: `{subdir or '(root)'}`")
    lines.append(f"- **Files analyzed**: {analysis.get('files_analyzed', 0)} / {analysis.get('files_considered', 0)}")
    lines.append("")

    if ext_counts:
        lines.append("### Extension Counts")
        for k, v in ext_counts.items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")

    if top_tree:
        lines.append("### Top-level Structure")
        lines.append("```")
        lines.append(top_tree)
        lines.append("```")
        lines.append("")

    # Per-file sections
    for item in analysis.get('results', []) or []:
        path = item.get('path', '')
        status = item.get('status', '')
        lines.append(f"## File: `{path}` — {status.upper()}")
        if status != 'reviewed':
            reason = item.get('reason') or item.get('error') or 'Not reviewed'
            lines.append("")
            lines.append(f"> {reason}")
            lines.append("")
            continue

        result = item.get('result', {}) or {}
        analysis_results = result.get('analysis_results', {}) or {}

        # Security
        sec = analysis_results.get('security') or {}
        lines.append("### Security")
        _append_issue_section(lines, sec)
        # Maintainability
        main = analysis_results.get('maintainability') or {}
        lines.append("### Maintainability")
        _append_issue_section(lines, main)
        # Style
        sty = analysis_results.get('style') or {}
        lines.append("### Style")
        _append_issue_section(lines, sty)
        # Synthesis
        fb = (result.get('feedback') or '').strip()
        if fb:
            lines.append("### Reviewer Notes")
            lines.append(fb)
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _append_issue_section(lines: List[str], section: Dict[str, Any]) -> None:
    issues = (section or {}).get('issues') or []
    if not issues:
        lines.append("- **No issues found.**")
        lines.append("")
        return
    for i, iss in enumerate(issues, 1):
        title = iss.get('title') or f"Issue {i}"
        sev = (iss.get('severity') or 'medium').upper()
        desc = (iss.get('description') or iss.get('error') or '').strip()
        lines.append(f"- **[{sev}] {title}**")
        if desc:
            lines.append(f"  - {desc}")
    lines.append("")
