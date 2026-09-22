from __future__ import annotations

from neo4j import AsyncGraphDatabase


async def check_neo4j(uri: str, user: str, password: str) -> bool:
    driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
    try:
        await driver.verify_connectivity()
        return True
    finally:
        await driver.close()
