import hashlib
import hmac
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from incidentgraph.config import PrincipalConfig


class Principal(BaseModel):
    principal_id: str
    roles: frozenset[str]
    service_ids: frozenset[str]


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenAuthenticator:
    def __init__(self, token_hashes: dict[str, PrincipalConfig]) -> None:
        self._token_hashes = token_hashes

    def authenticate(self, token: str) -> Principal | None:
        supplied = hash_token(token)
        for expected, config in self._token_hashes.items():
            if hmac.compare_digest(supplied, expected):
                return Principal(
                    principal_id=config.principal_id,
                    roles=config.roles,
                    service_ids=config.service_ids,
                )
        return None


def principal_dependency(
    authenticator: TokenAuthenticator,
) -> Callable[..., Principal]:
    bearer = HTTPBearer(auto_error=False)

    def require_principal(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Depends(bearer),
        ],
    ) -> Principal:
        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing bearer token",
            )
        principal = authenticator.authenticate(credentials.credentials)
        if principal is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid bearer token",
            )
        return principal

    return require_principal
