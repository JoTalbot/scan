import json
import subprocess
import sys


def test_public_report_redacts_sensitive_fields(tmp_path):
    source = tmp_path / "findings.jsonl"
    output = tmp_path / "public.json"
    source.write_text(
        json.dumps({
            "ip": "192.0.2.10",
            "vendor": "Example",
            "username": "admin",
            "password": "secret-value",
            "auth_method": "basic",
        }) + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [sys.executable, "scripts/public_report.py", str(source), str(output)],
        check=True,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    finding = report["findings"][0]
    assert finding["target_id"].startswith("sha256:")
    assert "192.0.2.10" not in json.dumps(report)
    assert "secret-value" not in json.dumps(report)
    assert "username" not in finding
