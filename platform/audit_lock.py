"""The verdict on pip-audit's JSON report of the framework's lock (D234), read on stdin.

A known vulnerability that a published version fixes fails: the lock can move past it, and
Dependabot's security updates open that pull request. One with no fix yet is said, as a warning
on the forge's check, and passes: no pull request could make it green, and a required check red
for every change until upstream releases would stop the repository for nothing it can do. A
package the audit could not read, or a report that is not one, fails: unread is never clean.
"""

from __future__ import annotations

import json
import sys


def verdict(report: str) -> tuple[int, list[str]]:
    try:
        dependencies = json.loads(report)["dependencies"]
    except (ValueError, KeyError, TypeError):
        return 1, ["FAIL the audit gave no report: nothing was judged."]
    lines, code = [], 0
    for dependency in dependencies:
        name, version = dependency.get("name"), dependency.get("version")
        if dependency.get("skip_reason"):
            code = 1
            lines.append(f"FAIL {name} not audited: {dependency['skip_reason']}")
        for vuln in dependency.get("vulns", []):
            fixes = vuln.get("fix_versions") or []
            if fixes:
                code = 1
                lines.append(f"FAIL {name} {version}: {vuln['id']}, fixed in {', '.join(fixes)}. "
                             f"Action: uv lock --upgrade-package {name}.")
            else:
                lines.append(f"::warning title=No fix yet::{name} {version}: {vuln['id']} has no fixed release; "
                             "said here until one is published.")
    if not lines:
        lines.append(f"No known vulnerability in the {len(dependencies)} locked packages.")
    return code, lines


if __name__ == "__main__":
    code, lines = verdict(sys.stdin.read())
    print("\n".join(lines))
    sys.exit(code)
