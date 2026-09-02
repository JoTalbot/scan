from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


FORBIDDEN_TRACKED_PATHS = {
    "data/creds/router_default_creds.csv",
}

FORBIDDEN_SUFFIXES = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
)


def _tracked_files():
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [p for p in result.stdout.decode().split("\0") if p]


def test_forbidden_credential_artifacts_are_not_tracked():
    tracked = _tracked_files()
    violations = []
    for path in tracked:
        normalized = path.replace("\\", "/")
        name = Path(normalized).name.lower()
        if normalized in FORBIDDEN_TRACKED_PATHS:
            violations.append(normalized)
        elif name.startswith("router_credentials_") and not name.startswith("router_credentials_summary_"):
            violations.append(normalized)
        elif normalized.startswith("data/raw/"):
            violations.append(normalized)
        elif normalized.startswith("data/creds/") and name.endswith((".csv", ".csv.gz")) and "summary" not in name:
            violations.append(normalized)
        elif name.endswith(FORBIDDEN_SUFFIXES):
            violations.append(normalized)
    assert not violations, f"Forbidden credential/private artifacts are tracked: {violations}"


def test_public_policy_files_exist():
    for relative in ("SECURITY_POLICY.md", "docs/PUBLIC_REPORTING.md"):
        assert (ROOT / relative).is_file()
