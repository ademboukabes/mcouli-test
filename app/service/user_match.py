from __future__ import annotations

from uuid import UUID

from db.generated import user as user_queries
from app.schema.internal.single_face_match import ClosestUserMatch


class UserMatchService:
    def __init__(self, *, user_querier: user_queries.AsyncQuerier) -> None:
        self.user_querier = user_querier

    async def find_closest_user(self, *, embedding_literal: str) -> ClosestUserMatch | None:
        row = await self.user_querier.find_closest_user_by_embedding(
            dollar_1=embedding_literal,
        )
        if row is None or row.distance is None:
            return None
        return ClosestUserMatch(user_id=row.id, distance=float(row.distance))
