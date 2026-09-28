from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "create_local_env.py"
    spec = importlib.util.spec_from_file_location("create_local_env", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_replaces_placeholders_and_scopes_operator() -> None:
    module = _module()
    template = (
        "INCIDENTGRAPH_APP_DB_PASSWORD=CHANGE_ME\n"
        "INCIDENTGRAPH_LAB_DB_PASSWORD=CHANGE_ME\n"
        "INCIDENTGRAPH_APP_DATABASE_DSN=x\n"
        "INCIDENTGRAPH_LAB_DATABASE_DSN=x\n"
        "INCIDENTGRAPH_NEO4J_PASSWORD=CHANGE_ME\n"
        "INCIDENTGRAPH_LAB_CONTROL_TOKEN=CHANGE_ME\n"
        "INCIDENTGRAPH_AUTH_TOKENS_JSON={}\n"
    )

    rendered = module.render(template, "known-token")
    values = dict(line.split("=", 1) for line in rendered.splitlines())
    auth = json.loads(values["INCIDENTGRAPH_AUTH_TOKENS_JSON"])

    assert "CHANGE_ME" not in rendered
    assert values["INCIDENTGRAPH_APP_DB_PASSWORD"] in values["INCIDENTGRAPH_APP_DATABASE_DSN"]
    assert values["INCIDENTGRAPH_LAB_DB_PASSWORD"] in values["INCIDENTGRAPH_LAB_DATABASE_DSN"]
    assert list(auth.values())[0]["roles"] == ["viewer", "reviewer", "operator"]
    assert list(auth.values())[0]["service_ids"] == [
        "svc-gateway",
        "svc-checkout",
        "svc-payments",
    ]
