"""Create an ignored local .env with independent random secrets and one scoped operator."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render(template: str, token: str) -> str:
    app_password = secrets.token_urlsafe(32)
    lab_password = secrets.token_urlsafe(32)
    neo4j_password = secrets.token_urlsafe(32)
    control_token = secrets.token_urlsafe(40)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    auth = json.dumps(
        {
            token_hash: {
                "principal_id": "local-operator",
                "roles": ["viewer", "reviewer", "operator"],
                "service_ids": ["svc-gateway", "svc-checkout", "svc-payments"],
            }
        },
        separators=(",", ":"),
    )
    replacements = {
        "INCIDENTGRAPH_APP_DB_PASSWORD": app_password,
        "INCIDENTGRAPH_LAB_DB_PASSWORD": lab_password,
        "INCIDENTGRAPH_APP_DATABASE_DSN": (
            f"postgresql://incidentgraph:{app_password}@127.0.0.1:55432/incidentgraph"
        ),
        "INCIDENTGRAPH_LAB_DATABASE_DSN": (f"postgresql://lab:{lab_password}@127.0.0.1:55433/lab"),
        "INCIDENTGRAPH_NEO4J_PASSWORD": neo4j_password,
        "INCIDENTGRAPH_LAB_CONTROL_TOKEN": control_token,
        "INCIDENTGRAPH_AUTH_TOKENS_JSON": auth,
    }
    rendered: list[str] = []
    for line in template.splitlines():
        key = line.partition("=")[0]
        rendered.append(f"{key}={replacements[key]}" if key in replacements else line)
    return "\n".join(rendered) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / ".env")
    parser.add_argument("--token", help="fixed token for automation; generated when omitted")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and not args.force:
        raise SystemExit(f"Refusing to overwrite {output}; pass --force explicitly.")
    token = args.token or secrets.token_urlsafe(32)
    template = (ROOT / ".env.example").read_text(encoding="utf-8")
    output.write_text(render(template, token), encoding="utf-8")
    output.chmod(0o600)
    print(json.dumps({"env_file": str(output), "bearer_token": token}, indent=2))
    print("Store the bearer token outside Git; it cannot be recovered from .env.")


if __name__ == "__main__":
    main()
