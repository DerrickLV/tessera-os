"""Read-only Microsoft Graph and SharePoint integration boundary."""

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .schemas import SourceDocument, UserContext


class IntegrationError(RuntimeError):
    pass


class GraphThrottleError(IntegrationError):
    def __init__(self, retry_after: float) -> None:
        super().__init__("Microsoft Graph throttled the read request")
        self.retry_after = retry_after


@dataclass(frozen=True)
class GraphPage:
    values: list[dict[str, Any]]
    next_link: str | None


class MicrosoftGraphReader:
    """Delegated-token Graph client exposing GET requests only."""

    base_url = "https://graph.microsoft.com/v1.0"

    def __init__(self, token_provider: Callable[[], str], *,
                 transport: Callable[[str, dict[str, str]], dict[str, Any]] | None = None,
                 max_retries: int = 2,
                 sleeper: Callable[[float], None] = time.sleep) -> None:
        self._token_provider = token_provider
        self._transport = transport or self._get_json
        self._max_retries = max_retries
        self._sleeper = sleeper

    @staticmethod
    def _get_json(url: str, headers: dict[str, str]) -> dict[str, Any]:
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except HTTPError as exc:
            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After", "1")
                try:
                    delay = max(0.0, float(retry_after))
                except ValueError:
                    delay = 1.0
                raise GraphThrottleError(delay) from exc
            raise IntegrationError("Microsoft Graph read failed") from exc
        except Exception as exc:
            raise IntegrationError("Microsoft Graph read failed") from exc

    def _pages(self, path: str, params: dict[str, str] | None = None) -> Iterator[GraphPage]:
        url = path if path.startswith(self.base_url) else f"{self.base_url}/{path.lstrip('/')}"
        if params:
            url = f"{url}?{urlencode(params)}"
        headers = {"Authorization": f"Bearer {self._token_provider()}", "Accept": "application/json"}
        while url:
            if not url.startswith(f"{self.base_url}/"):
                raise IntegrationError("Graph pagination escaped the approved origin")
            for attempt in range(self._max_retries + 1):
                try:
                    payload = self._transport(url, headers)
                    break
                except GraphThrottleError as exc:
                    if attempt >= self._max_retries:
                        raise
                    self._sleeper(exc.retry_after)
            yield GraphPage(payload.get("value", []), payload.get("@odata.nextLink"))
            url = payload.get("@odata.nextLink")

    def calendar_events(self, *, start: str, end: str) -> list[dict[str, Any]]:
        params = {"startDateTime": start, "endDateTime": end,
                  "$select": "id,subject,start,end,location,organizer,webLink",
                  "$orderby": "start/dateTime"}
        return [item for page in self._pages("me/calendarView", params) for item in page.values]

    def recent_messages(self, *, limit: int = 25) -> list[dict[str, Any]]:
        params = {"$top": str(min(limit, 100)),
                  "$select": "id,subject,from,receivedDateTime,importance,webLink,bodyPreview",
                  "$orderby": "receivedDateTime desc"}
        return [item for page in self._pages("me/messages", params) for item in page.values][:limit]

    def sharepoint_documents(self, *, site_id: str, drive_id: str,
                             context: UserContext, project_id: str,
                             folder_item_id: str = "root") -> list[SourceDocument]:
        if project_id not in context.project_ids:
            raise PermissionError(f"User is not authorized for project {project_id!r}")
        item_path = "root" if folder_item_id == "root" else f"items/{folder_item_id}"
        path = f"sites/{site_id}/drives/{drive_id}/{item_path}/children"
        params = {"$select": "id,name,webUrl,lastModifiedDateTime,file,listItem",
                  "$expand": "listItem($expand=fields)"}
        documents: list[SourceDocument] = []
        for page in self._pages(path, params):
            for item in page.values:
                fields = item.get("listItem", {}).get("fields", {})
                if fields.get("ProjectId") != project_id or "file" not in item:
                    continue
                documents.append(SourceDocument(
                    source_id=item["id"], tenant_id=context.tenant_id, project_id=project_id,
                    title=item["name"], content=fields.get("TesseraContent", ""),
                    web_url=item.get("webUrl"),
                    modified_at=datetime.fromisoformat(item["lastModifiedDateTime"])
                    if item.get("lastModifiedDateTime") else None,
                    allowed_user_ids=frozenset(item.get("allowedUserIds", [])),
                    allowed_group_ids=frozenset(item.get("allowedGroupIds", [])),
                    metadata={"site_id": site_id, "drive_id": drive_id}))
        return documents
