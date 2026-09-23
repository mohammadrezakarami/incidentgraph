from incidentgraph.auth import TokenAuthenticator, hash_token
from incidentgraph.config import PrincipalConfig


def test_authenticator_accepts_only_matching_hash() -> None:
    token = "a-long-test-token-that-is-not-a-real-secret"
    authenticator = TokenAuthenticator(
        {
            hash_token(token): PrincipalConfig(
                principal_id="viewer-1",
                roles=frozenset({"viewer"}),
                service_ids=frozenset({"svc-gateway"}),
            )
        }
    )

    principal = authenticator.authenticate(token)

    assert principal is not None
    assert principal.principal_id == "viewer-1"
    assert principal.service_ids == frozenset({"svc-gateway"})
    assert authenticator.authenticate("wrong-token") is None
