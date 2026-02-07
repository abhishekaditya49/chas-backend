"""Declaration and witness business logic."""

from __future__ import annotations

from typing import Any

from postgrest import APIError

from app.services.common import SupabaseService, map_users_on_field
from app.utils.errors import ConflictError, NotFoundError
from supabase import Client


class DeclarationService:
    """Manage declarations and witness interactions."""

    def __init__(self, client: Client) -> None:
        self.db = SupabaseService(client)

    def create_declaration(
        self,
        user_id: str,
        community_id: str,
        title: str,
        description: str,
        cc_spent: int,
    ) -> dict[str, Any]:
        """Create a declaration row."""
        return self.db.insert_one(
            "declarations",
            {
                "user_id": user_id,
                "community_id": community_id,
                "title": title,
                "description": description,
                "cc_spent": cc_spent,
            },
        )

    def get(self, declaration_id: str) -> dict[str, Any]:
        """Return a declaration by id."""
        return self.db.select_one(
            "declarations",
            {"id": declaration_id},
            not_found_label="Declaration",
        )

    def list_for_gazette(
        self,
        community_id: str,
        current_user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return declaration rows enriched for gazette consumption."""
        declarations = self.db.select_many(
            "declarations",
            filters={"community_id": community_id},
            order_by="created_at",
            descending=True,
            limit=limit,
            offset=offset,
        )
        total = self.db.count("declarations", {"community_id": community_id})
        if not declarations:
            return [], total

        declaration_ids = [str(row["id"]) for row in declarations]
        witnesses = self.db.execute(
            self.db.client.table("witnesses")
            .select("user_id,declaration_id")
            .in_("declaration_id", declaration_ids),
            default=[],
        )

        count_map: dict[str, int] = {}
        user_witnessed: set[str] = set()
        for witness in witnesses:
            dec_id = str(witness["declaration_id"])
            count_map[dec_id] = count_map.get(dec_id, 0) + 1
            if str(witness["user_id"]) == current_user_id:
                user_witnessed.add(dec_id)

        users = self.db.get_users_map([str(row["user_id"]) for row in declarations])
        payload: list[dict[str, Any]] = []
        for row in declarations:
            declaration_id = str(row["id"])
            entry = dict(row)
            entry["witnessed_count"] = count_map.get(declaration_id, 0)
            entry["has_witnessed"] = declaration_id in user_witnessed
            payload.append(entry)

        return map_users_on_field(payload, users), total

    def witness(self, user_id: str, declaration_id: str) -> int:
        """Create a witness row and return updated witness count."""
        self.get(declaration_id)

        existing = self.db.select_many(
            "witnesses",
            filters={"user_id": user_id, "declaration_id": declaration_id},
            limit=1,
        )
        if existing:
            raise ConflictError("Declaration already witnessed")

        try:
            self.db.insert_one(
                "witnesses",
                {"user_id": user_id, "declaration_id": declaration_id},
            )
        except APIError as exc:
            message = str(getattr(exc, "message", ""))
            if "duplicate" in message.lower() or "unique" in message.lower():
                raise ConflictError("Declaration already witnessed") from exc
            raise

        response = (
            self.db.client.table("witnesses")
            .select("user_id", count="exact")
            .eq("declaration_id", declaration_id)
            .execute()
        )
        return response.count or 0

    def declaration_with_author(self, declaration_id: str, current_user_id: str) -> dict[str, Any]:
        """Return one declaration enriched with witness metadata and author."""
        declaration = self.get(declaration_id)
        witness_rows = self.db.execute(
            self.db.client.table("witnesses")
            .select("user_id")
            .eq("declaration_id", declaration_id),
            default=[],
        )
        declaration["witnessed_count"] = len(witness_rows)
        declaration["has_witnessed"] = any(
            str(row["user_id"]) == current_user_id for row in witness_rows
        )
        declaration["user"] = self.db.get_user(str(declaration["user_id"]))
        return declaration

    def get_author_id(self, declaration_id: str) -> str:
        """Return declaration author's user id."""
        declaration = self.get(declaration_id)
        author_id = declaration.get("user_id")
        if not author_id:
            raise NotFoundError("Declaration")
        return str(author_id)
