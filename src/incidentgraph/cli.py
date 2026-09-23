from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import secrets
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from incidentgraph.auth import hash_token
from incidentgraph.config import Settings
from incidentgraph.health import check_neo4j
from incidentgraph.logging import configure_logging
from incidentgraph.models import InvestigationCreate, InvestigationMode
from incidentgraph.persistence import Database
from incidentgraph.worker import run_worker_once

ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "ops" / "migrations"


def load_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        print("Configuration error:", file=sys.stderr)
        print(exc, file=sys.stderr)
        raise SystemExit(2) from exc


def doctor() -> int:
    settings = load_settings()
    problems = settings.validate_runtime()
    result = {
        "status": "ok" if not problems else "invalid",
        "environment": settings.environment,
        "api_bind": f"{settings.api_host}:{settings.api_port}",
        "model_provider": settings.model_provider,
        "problems": problems,
    }
    print(json.dumps(result, indent=2))
    return 0 if not problems else 2


def token_command(generate: bool) -> int:
    token = secrets.token_urlsafe(32) if generate else getpass.getpass("Token (input hidden): ")
    print(json.dumps({"token": token if generate else "<hidden>", "sha256": hash_token(token)}))
    return 0


async def migrate(settings: Settings) -> None:
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        paths = [
            path
            for path in sorted(MIGRATIONS.glob("*.sql"))
            if not path.stem.endswith("_lab")
        ]
        if not paths:
            raise RuntimeError("no database migrations were found")
        for path in paths:
            await database.apply_migration(path)
    finally:
        await database.close()
    print(f"applied {len(paths)} migrations: {', '.join(path.stem for path in paths)}")


async def check_connections(settings: Settings) -> None:
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        postgres_ok = await database.ping()
    finally:
        await database.close()
    neo4j_ok = await check_neo4j(
        settings.neo4j_uri,
        settings.neo4j_user,
        settings.neo4j_password.get_secret_value(),
    )
    print(json.dumps({"postgres": postgres_ok, "neo4j": neo4j_ok}))


async def enqueue_test(settings: Settings) -> None:
    now = datetime.now(UTC)
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        accepted = await database.create_investigation(
            owner_id="local-operator",
            request_id=uuid4(),
            idempotency_key=f"cli-{uuid4()}",
            request=InvestigationCreate(
                question="Verify durable non-AI worker execution for the local foundation.",
                target_service="gateway",
                environment="lab",
                window_start=now - timedelta(minutes=5),
                window_end=now,
                mode=InvestigationMode.REPLAY,
            ),
        )
    finally:
        await database.close()
    print(accepted.model_dump_json())


async def retention(settings: Settings, apply: bool) -> None:
    database = Database(settings.app_database_dsn.get_secret_value())
    await database.open()
    try:
        preview = await database.event_retention_status(settings.event_retention_days)
        if apply:
            preview["deleted_count"] = await database.prune_event_history(
                settings.event_retention_days
            )
            preview["applied"] = True
        else:
            preview["applied"] = False
    finally:
        await database.close()
    print(json.dumps(preview, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="incidentgraph")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("doctor")
    subcommands.add_parser("hash-token")
    subcommands.add_parser("generate-token")
    subcommands.add_parser("migrate")
    subcommands.add_parser("check-connections")
    subcommands.add_parser("enqueue-test")
    subcommands.add_parser("worker-once")
    retention_parser = subcommands.add_parser("retention")
    retention_parser.add_argument(
        "--apply",
        action="store_true",
        help="delete only event rows older than EVENT_RETENTION_DAYS",
    )
    args = parser.parse_args()

    if args.command == "doctor":
        raise SystemExit(doctor())
    if args.command == "hash-token":
        raise SystemExit(token_command(generate=False))
    if args.command == "generate-token":
        raise SystemExit(token_command(generate=True))

    settings = load_settings()
    configure_logging(settings.log_level)
    if args.command == "migrate":
        asyncio.run(migrate(settings))
    elif args.command == "check-connections":
        asyncio.run(check_connections(settings))
    elif args.command == "enqueue-test":
        asyncio.run(enqueue_test(settings))
    elif args.command == "worker-once":
        raise SystemExit(0 if asyncio.run(run_worker_once(settings)) else 2)
    elif args.command == "retention":
        asyncio.run(retention(settings, args.apply))
