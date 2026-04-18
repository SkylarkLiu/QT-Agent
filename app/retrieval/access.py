from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RetrievalAccessScope:
    user_id: str | None = None
    tenant_id: str | None = None
    accessible_kb_ids: list[str] = field(default_factory=list)

    def to_metadata_filter(self, *, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        filters: dict[str, Any] = {}
        if self.user_id:
            filters["owner_user_id"] = self.user_id
        if self.tenant_id:
            filters["tenant_id"] = self.tenant_id
        if self.accessible_kb_ids:
            filters["kb_id"] = self.accessible_kb_ids
        if extra:
            filters.update(extra)
        return filters
