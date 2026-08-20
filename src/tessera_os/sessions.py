"""The signed portal session, and the identity it carries.

This lives in its own module because two applications need it and neither
should import the other. The portal *issues* the session at the end of the
Microsoft sign-in; the console *verifies* it on every request. Leaving the
codec inside ``portal.py`` forced the console to import the portal in order to
read a cookie, and the portal to import the console in order to mount it —
a cycle whose usual resolution is a deferred import that hides the dependency
rather than removing it.

The session is a signed JWT in an ``HttpOnly``, ``Secure``, ``SameSite=Lax``
cookie. Two properties of that choice run through the rest of the system:

- **The browser can read the claims but cannot mint them.** ``grp`` carries the
  *mapped Tessera* groups, resolved once at sign-in through the Entra group
  map. A user cannot add themselves to ``qualified_counsel`` by editing a
  cookie, because the signature is produced with a secret the browser never
  sees.
- **Lax means same-origin.** A browser will not attach a Lax cookie to a
  cross-origin request. Every surface that needs this session must therefore be
  served from the portal's own origin — which is why the console is mounted on
  the portal rather than deployed beside it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status

COOKIE_NAME = "tessera_session"
SESSION_HOURS = 8


class SessionCodec:
    issuer = "tessera-portal"
    audience = "tessera-portal-browser"

    def __init__(self, secret: str) -> None:
        self.secret = secret

    def issue(self, *, user_id: str, tenant_id: str, display_name: str,
              group_ids: list[str] | None = None) -> str:
        now = datetime.now(UTC)
        # ``grp`` carries the *mapped Tessera* groups, resolved once at sign-in
        # through the Entra group map. The browser can read the cookie's claims
        # but cannot mint them — the session is signed server-side.
        return jwt.encode({"sub": user_id, "tid": tenant_id, "name": display_name,
            "grp": sorted(group_ids or []),
            "iss": self.issuer, "aud": self.audience, "iat": now,
            "exp": now + timedelta(hours=SESSION_HOURS)}, self.secret, algorithm="HS256")

    def decode(self, token: str) -> dict[str, str]:
        try:
            return jwt.decode(token, self.secret, algorithms=["HS256"],
                issuer=self.issuer, audience=self.audience,
                options={"require": ["sub", "tid", "iss", "aud", "iat", "exp"]})
        except jwt.PyJWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Portal session is invalid or expired") from exc
