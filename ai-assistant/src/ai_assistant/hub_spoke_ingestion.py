"""
Hub and Spoke Ingestion: Data Sanitization and Enrichment
==========================================================

Handles:
1. SEO Spam Defense (sanitize_input)
2. Granularity Enrichment (enrich_text)
3. Bidirectional Linking (User ↔ Competence)
"""
import re
import logging
from datetime import datetime, UTC
from typing import Any

from ai_assistant.hub_spoke_schema import (
    get_user_collection,
    get_competence_collection
)
from ai_assistant.firestore_schemas import derive_availability_tags
from weaviate.classes.query import Filter

logger = logging.getLogger(__name__)


def sanitize_input(text: str, max_unique_words: int = 20, max_chars: int = 200) -> str:
    """
    SEO Spam Defense: Strip keyword stuffing from input text.

    Strategy:
    1. Extract unique words (case-insensitive)
    2. If unique word count > threshold, it's likely spam — truncate to first N unique words
    3. Cap result at max_chars to prevent a single massive word from
       overloading the embedding model (e.g. a 10 000-char wordless blob).

    Args:
        text: Input text to sanitize
        max_unique_words: Maximum unique words allowed before truncation
        max_chars: Hard character-length cap applied after word deduplication.

    Returns:
        Sanitized text
    """
    if not text or not text.strip():
        return ""

    # Split into words and normalize
    words = re.findall(r'\b\w+\b', text.lower())

    # Get unique words while preserving order
    seen = set()
    unique_words = []
    for word in words:
        if word not in seen:
            seen.add(word)
            unique_words.append(word)

    # If too many unique words, it's likely spam - truncate
    if len(unique_words) > max_unique_words:
        logger.warning("Keyword stuffing detected: %s unique words. Truncating.", len(unique_words))
        # Reconstruct from original text to maintain case and punctuation
        result = ' '.join(unique_words[:max_unique_words])
    else:
        result = text

    # B5: Hard character-length cap to prevent a single massive word (or long
    # concatenated tokens) from overloading the embedding model.
    if len(result) > max_chars:
        # Truncate at nearest space before the limit to avoid mid-word cuts.
        truncated_at_space = result[:max_chars + 1].rsplit(' ', 1)[0]
        result = truncated_at_space if truncated_at_space else result[:max_chars]
        logger.warning(
            "sanitize_input: text exceeded %d chars after dedup — truncated to %d chars",
            max_chars, len(result),
        )

    return result


def enrich_text(text: str, category: str) -> str:
    """
    Granularity Enrichment: Expand specific skill text with parent categories.

    Strategy:
    1. Map categories to parent terms
    2. Append parent terms to original text
    3. Improves recall for broad searches

    Example:
        Input: text="Installing Pot Lights", category="Electrical"
        Output: "Installing Pot Lights Electrician Electrical Lighting Wiring"

    This ensures a search for "Electrician" matches specific skills like "Pot Lights"

    Args:
        text: Original skill description
        category: Skill category

    Returns:
        Enriched text with parent category terms
    """
    # Category enrichment map: category -> parent terms
    _IT_TERMS = ["Technician", "Technology", "Computer", "Software", "Hardware"]
    enrichment_map = {
        "Electrical": ["Electrician", "Electrical", "Lighting", "Wiring", "Power"],
        "Plumbing": ["Plumber", "Plumbing", "Pipes", "Water", "Drain"],
        "Gardening": ["Gardener", "Gardening", "Landscaping", "Plants", "Outdoor"],
        "Carpentry": ["Carpenter", "Carpentry", "Woodwork", "Construction"],
        "Cleaning": ["Cleaner", "Cleaning", "Housekeeping", "Janitorial"],
        "IT": _IT_TERMS,
        # Aliases — all map to the same IT bucket
        "Technology": _IT_TERMS + ["Mobile", "App", "Development"],
        "App Development": _IT_TERMS + ["Mobile", "App", "Development", "Flutter", "React", "Android", "iOS"],
        "Mobile Development": _IT_TERMS + ["Mobile", "App", "Development", "Flutter", "Android", "iOS"],
    }

    # Get parent terms for category
    parent_terms = enrichment_map.get(category, [category])

    # Append parent terms to original text
    enriched = f"{text} {' '.join(parent_terms)}"

    logger.debug("Enriched '%s' → '%s'", text, enriched)
    return enriched


class HubSpokeIngestion:
    """
    Ingestion manager for Hub and Spoke architecture.

    Handles:
    1. Creating User (Hub)
    2. Creating Competence (Spoke)
    3. Establishing bidirectional links
    """

    @staticmethod
    def create_user(user_data: dict[str, Any]) -> str | None:
        """
        Creates a User (Hub).

        Args:
            user_data: Dict with keys: name, email, fcm_token,
                         has_open_request, last_sign_in

        Returns:
            UUID of added user
        """
        try:
            collection = get_user_collection()

            # Handle last_sign_in: can be datetime or days offset
            last_active = user_data.get("last_sign_in")
            if isinstance(last_active, int):
                # Treat as days ago
                from datetime import timedelta
                last_active = datetime.now(UTC) - timedelta(days=last_active)
            elif not isinstance(last_active, datetime):
                last_active = datetime.now(UTC)

            uuid = collection.data.insert(
                properties={
                    "name": user_data.get("name"),
                    "email": user_data.get("email"),
                    "location": user_data.get("location", ""),
                    "user_id": user_data.get("user_id"),
                    "self_introduction": user_data.get("self_introduction", ""),
                    "is_service_provider": user_data.get("is_service_provider", False),
                    "fcm_token": user_data.get("fcm_token", ""),
                    "feedback_positive": user_data.get("feedback_positive", []),
                    "feedback_negative": user_data.get("feedback_negative", []),
                    "average_rating": user_data.get("average_rating", 0.0),
                    "review_count": user_data.get("review_count", 0),
                    "created_at": user_data.get("created_at", datetime.now(UTC)),
                    "has_open_request": user_data.get("has_open_request", False),
                    "last_sign_in": last_active,
                    "source": user_data.get("source", ""),
                    "phone": user_data.get("phone", ""),
                    "website": user_data.get("website", ""),
                    "address": user_data.get("address", ""),
                }
            )

            logger.info("Created User: %s (UUID: %s)", user_data.get('name'), uuid)
            return str(uuid)

        except Exception as e:
            logger.error("Error creating user: %s", e)
            return None

    @staticmethod
    def upsert_user(
        user_data: dict[str, Any],
        competence_data: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Insert or update a User (Hub) node using a deterministic UUID.

        The UUID must be pre-computed by the caller (e.g.
        ``weaviate.util.generate_uuid5(place_id)``).  If an object with that
        UUID already exists it is replaced in-place; no duplicate is created.

        Optionally creates / updates an associated Competence (Spoke) node using
        a second deterministic UUID derived from the same place_id.

        Args:
            user_data: Must include ``"uuid"`` (string).  Other keys mirror
                       ``create_user()`` with the addition of ``"source"``,
                       ``"phone"``, ``"website"``, ``"address"``.
            competence_data: When provided, the associated Competence node is
                             upserted.  Must include ``"uuid"`` (string) and
                             ``"search_optimized_summary"``.

        Returns:
            UUID of the user node (same as ``user_data["uuid"]``), or None on
            error.
        """
        from weaviate.exceptions import UnexpectedStatusCodeError

        user_uuid = user_data.get("uuid", "")
        if not user_uuid:
            logger.error("upsert_user: 'uuid' is required in user_data")
            return None

        user_props: dict[str, Any] = {
            "name": user_data.get("name", ""),
            "email": user_data.get("email") or "",
            "location": user_data.get("location", ""),
            "user_id": user_data.get("user_id") or None,
            "self_introduction": user_data.get("self_introduction", ""),
            "is_service_provider": user_data.get("is_service_provider", True),
            "fcm_token": "",
            "feedback_positive": [],
            "feedback_negative": [],
            "average_rating": float(user_data.get("average_rating") or 0.0),
            "review_count": 0,
            "created_at": user_data.get("created_at", datetime.now(UTC)),
            "has_open_request": False,
            # last_sign_in intentionally None so ghost-filter is_none() passes.
            "last_sign_in": None,
            "source": user_data.get("source", ""),
            "phone": user_data.get("phone") or "",
            "website": user_data.get("website") or "",
            "address": user_data.get("address") or "",
            "photo_url": user_data.get("photo_url") or "",
            "opening_hours": user_data.get("opening_hours") or "",
            "maps_url": user_data.get("maps_url") or "",
        }

        try:
            user_collection = get_user_collection()
            try:
                user_collection.data.insert(properties=user_props, uuid=user_uuid)
                logger.info("upsert_user: inserted GP User '%s' (UUID: %s)", user_data.get("name"), user_uuid)
            except UnexpectedStatusCodeError:
                # Object already exists — patch in-place (PATCH preserves cross-references).
                user_collection.data.update(uuid=user_uuid, properties=user_props)
                logger.info("upsert_user: updated GP User '%s' (UUID: %s)", user_data.get("name"), user_uuid)
            except Exception as insert_exc:
                err_str = str(insert_exc).lower()
                if "already exist" in err_str or "conflict" in err_str or "422" in err_str:
                    user_collection.data.update(uuid=user_uuid, properties=user_props)
                    logger.info("upsert_user: replaced GP User '%s' (UUID: %s)", user_data.get("name"), user_uuid)
                else:
                    raise

            if competence_data:
                comp_uuid = competence_data.get("uuid", "")
                if not comp_uuid:
                    logger.error("upsert_user: 'uuid' is required in competence_data")
                    return str(user_uuid)

                comp_props: dict[str, Any] = {
                    "competence_id": competence_data.get("competence_id", ""),
                    "title": competence_data.get("title", ""),
                    "description": competence_data.get("description", ""),
                    "category": competence_data.get("category", ""),
                    "search_optimized_summary": competence_data.get("search_optimized_summary", ""),
                    "skills_list": competence_data.get("skills_list", []),
                    "price_per_hour": competence_data.get("price_per_hour") or 0.0,
                    "year_of_experience": 0,
                    "availability_tags": [],
                    "availability_text": "",
                    "review_snippets": competence_data.get("review_snippets") or [],
                }
                competence_collection = get_competence_collection()
                try:
                    competence_collection.data.insert(
                        properties=comp_props,
                        uuid=comp_uuid,
                        references={"owned_by": user_uuid},
                    )
                    logger.info("upsert_user: inserted GP Competence (UUID: %s)", comp_uuid)
                    # Bidirectional link: User → Competence
                    user_collection.data.reference_add(
                        from_uuid=user_uuid,
                        from_property="has_competencies",
                        to=comp_uuid,
                    )
                except UnexpectedStatusCodeError:
                    # PATCH preserves the owned_by cross-reference — replace() (PUT) would wipe it.
                    competence_collection.data.update(
                        uuid=comp_uuid,
                        properties=comp_props,
                    )
                    logger.info("upsert_user: updated GP Competence (UUID: %s)", comp_uuid)
                except Exception as comp_exc:
                    err_str = str(comp_exc).lower()
                    if "already exist" in err_str or "conflict" in err_str or "422" in err_str:
                        competence_collection.data.update(uuid=comp_uuid, properties=comp_props)
                        logger.info("upsert_user: replaced GP Competence (UUID: %s)", comp_uuid)
                    else:
                        raise

            return str(user_uuid)

        except Exception as e:
            logger.error("upsert_user: error upserting GP provider '%s': %s", user_data.get("name"), e)
            return None

    @staticmethod
    def update_user_hub_properties(user_id: str, update_data: dict[str, Any]) -> bool:
        """Update specific properties of a User hub node in Weaviate.

        Uses the hub-spoke schema User collection (not the legacy
        ``UserModelWeaviate`` collection) so that changes are visible to the
        search filters that traverse ``owned_by`` cross-references.

        Args:
            user_id:     Firestore / Firebase user identifier.
            update_data: Dict of property names → new values to merge into the
                         existing Weaviate object.

        Returns:
            True on success, False when the user node was not found or an error
            occurred.
        """
        try:
            user_collection = get_user_collection()
            result = user_collection.query.fetch_objects(
                filters=Filter.by_property("user_id").equal(user_id),
                limit=1,
            )
            if not result.objects:
                logger.warning(
                    "update_user_hub_properties: no Weaviate User found for user_id=%s",
                    user_id,
                )
                return False
            user_uuid = str(result.objects[0].uuid)
            user_collection.data.update(uuid=user_uuid, properties=update_data)
            logger.info(
                "Updated Weaviate User hub for user_id=%s: %s",
                user_id,
                list(update_data.keys()),
            )
            return True
        except Exception as e:
            logger.error(
                "Error updating Weaviate User hub properties for %s: %s", user_id, e
            )
            return False

    @staticmethod
    def create_competence(
        competence_data: dict[str, Any],
        user_uuid: str,
        apply_sanitization: bool = True,
        apply_enrichment: bool = True
    ) -> str | None:
        """
        Create a Competence (Spoke) with bidirectional link to User.

        Critical Logic:
        1. Sanitize description to prevent keyword stuffing
        2. Enrich description with parent category terms
        3. Create competence with owned_by reference to User
        4. Add competence reference to User's has_competencies

        Args:
            competence_data: Dict with keys: title, description, category, price_range
            user_uuid: UUID of the owning User
            apply_sanitization: Whether to sanitize description
            apply_enrichment: Whether to enrich description

        Returns:
            UUID of created competence
        """
        try:
            user_collection = get_user_collection()
            competence_collection = get_competence_collection()

            # Process description
            description = competence_data.get("description", "")
            category = competence_data.get("category", "")

            # ── search_optimized_summary — primary vector source ──────────────
            # If enrichment produced a summary, use it (sanitized for spam defense).
            # Fall back to enriching the raw description so legacy / non-enriched
            # competences still get a reasonable vector.
            raw_summary = competence_data.get("search_optimized_summary", "")
            if raw_summary:
                if apply_sanitization:
                    raw_summary = sanitize_input(raw_summary, max_unique_words=60)
                search_optimized_summary = raw_summary
            else:
                # Fallback: build a minimal summary from raw description.
                if apply_sanitization:
                    description = sanitize_input(description)
                if apply_enrichment and category:
                    description = enrich_text(description, category)
                search_optimized_summary = description  # best effort

            # Step 3: Create Competence with owned_by reference
            competence_uuid = competence_collection.data.insert(
                properties={
                    "competence_id": competence_data.get("competence_id", ""),
                    "title": competence_data.get("title"),
                    # Raw description stored for display; NOT the vector source.
                    "description": description,
                    "category": category,
                    # ── search / filter fields ──────────────────────────────
                    "search_optimized_summary": search_optimized_summary,
                    "skills_list": competence_data.get("skills_list", []),
                    "price_per_hour": competence_data.get("price_per_hour"),
                    "year_of_experience": competence_data.get("year_of_experience", 0),
                    # Use pre-computed availability_tags from enricher when present;
                    # derive from availability_time as a fallback.
                    "availability_tags": (
                        competence_data.get("availability_tags")
                        or derive_availability_tags(
                            competence_data.get("availability_time") or {}
                        )
                    ),
                    "availability_text": competence_data.get("availability_text", ""),
                },
                references={
                    "owned_by": user_uuid  # Link to User (Spoke → Hub)
                }
            )

            logger.info("Created Competence: %s (UUID: %s)", competence_data.get('title'), competence_uuid)

            # Step 4: Add reverse reference (Hub → Spoke)
            # Add competence to User's has_competencies list
            user_collection.data.reference_add(
                from_uuid=user_uuid,
                from_property="has_competencies",
                to=competence_uuid
            )

            logger.info("Linked User %s ↔ Competence %s", user_uuid, competence_uuid)
            return str(competence_uuid)

        except Exception as e:
            logger.error("Error creating competence: %s", e)
            return None

    @staticmethod
    def create_user_with_competencies(
        user_data: dict[str, Any],
        competencies_data: list[dict[str, Any]],
        apply_sanitization: bool = True,
        apply_enrichment: bool = True
    ) -> dict[str, Any] | None:
        """
        Create a complete User with multiple Competencies.

        Convenience method for bulk ingestion.

        Args:
            user_data: User properties
            competencies_data: List of competence properties
            apply_sanitization: Whether to sanitize descriptions
            apply_enrichment: Whether to enrich descriptions

        Returns:
            Dict with user_uuid and list of competence_uuids
        """
        try:
            # Create user
            user_uuid = HubSpokeIngestion.create_user(user_data)
            if not user_uuid:
                return None

            # Create competencies
            competence_uuids = []
            for comp_data in competencies_data:
                comp_uuid = HubSpokeIngestion.create_competence(
                    comp_data,
                    user_uuid,
                    apply_sanitization=apply_sanitization,
                    apply_enrichment=apply_enrichment
                )
                if comp_uuid:
                    competence_uuids.append(comp_uuid)

            result = {
                "user_uuid": user_uuid,
                "competence_uuids": competence_uuids
            }

            logger.info("Created user with %s competencies", len(competence_uuids))
            return result

        except Exception as e:
            logger.error("Error creating user with competencies: %s", e)
            return None

    @staticmethod
    def create_competencies_by_user_id(
        user_id: str,
        competencies: str | list[str],
        category: str = "",
        apply_sanitization: bool = True,
        apply_enrichment: bool = True
    ) -> dict[str, Any]:
        """
        Create new competencies for an existing user by user_id.

        Args:
            user_id: The user_id to create competencies for
            competencies: Single string or list of strings describing competencies
            category: Category for the competencies (optional)
            apply_sanitization: Whether to sanitize descriptions
            apply_enrichment: Whether to enrich descriptions

        Returns:
            Dict with success status and list of added competence UUIDs
        """
        try:
            user_collection = get_user_collection()

            # Find user by user_id
            from weaviate.classes.query import Filter
            result = user_collection.query.fetch_objects(
                filters=Filter.by_property("user_id").equal(user_id),
                limit=1
            )

            if not result.objects:
                logger.error("No user found with user_id: %s", user_id)
                return {"success": False, "error": "User not found", "added_uuids": []}

            user_uuid = str(result.objects[0].uuid)
            logger.info("Found user %s for user_id %s", user_uuid, user_id)

            # Normalize input to list
            if isinstance(competencies, str):
                competencies_list = [competencies]
            else:
                competencies_list = competencies

            # Add each competence
            added_uuids = []
            for comp_text in competencies_list:
                comp_data = {
                    "title": comp_text[:50] if len(comp_text) > 50 else comp_text,
                    "description": comp_text,
                    "category": category,
                    "price_range": ""
                }

                comp_uuid = HubSpokeIngestion.create_competence(
                    competence_data=comp_data,
                    user_uuid=user_uuid,
                    apply_sanitization=apply_sanitization,
                    apply_enrichment=apply_enrichment
                )

                if comp_uuid:
                    added_uuids.append(comp_uuid)
                    logger.info("Created competence: %s", comp_uuid)

            logger.info("Created %s competencies for user %s", len(added_uuids), user_id)
            return {
                "success": True,
                "added_uuids": added_uuids,
                "count": len(added_uuids)
            }

        except Exception as e:
            logger.error("Error creating competencies: %s", e)
            return {"success": False, "error": str(e), "added_uuids": []}

    @staticmethod
    def update_competencies_by_user_id(
        user_id: str,
        competencies: str | list[str] | list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Replace all Weaviate competencies for a user with fresh enriched data.

        Deletes every existing Competence spoke for *user_id* and re-inserts them
        from the supplied *competencies* list (typically read back from Firestore
        after enrichment).  Passes all filter / rank fields so Weaviate becomes a
        fully-featured search index.

        Args:
            user_id:      Firestore / Firebase user identifier.
            competencies: Accepts any of:
                          - A single string (converted to one competence dict).
                          - A list of strings (each converted to a competence dict).
                          - A list of dicts (preferred; enriched fields are written
                            as-is so the full Weaviate index is populated).

        Returns:
            Dict with ``success``, ``updated_uuids``, and ``count`` keys.
        """
        try:
            user_collection = get_user_collection()
            competence_collection = get_competence_collection()

            # Find user by user_id
            from weaviate.classes.query import Filter
            result = user_collection.query.fetch_objects(
                filters=Filter.by_property("user_id").equal(user_id),
                limit=1
            )

            if not result.objects:
                logger.error("No user found with user_id: %s", user_id)
                return {"success": False, "error": "User not found", "updated_uuids": []}

            user_uuid = str(result.objects[0].uuid)
            logger.info("Found user %s for user_id %s", user_uuid, user_id)

            # Normalise input to List[Dict] so the loop below is uniform.
            if isinstance(competencies, str):
                competencies_to_insert: list[dict[str, Any]] = [
                    {"title": competencies, "description": competencies}
                ]
            elif isinstance(competencies, list):
                competencies_to_insert = []
                for item in competencies:
                    if isinstance(item, dict):
                        competencies_to_insert.append(item)
                    elif isinstance(item, str):
                        competencies_to_insert.append(
                            {"title": item, "description": item}
                        )
                    else:
                        logger.warning(
                            "update_competencies_by_user_id: skipping unsupported entry type %r",
                            type(item),
                        )
            else:
                logger.warning(
                    "update_competencies_by_user_id: unexpected competencies type %r", type(competencies)
                )
                competencies_to_insert = []

            # Delete all existing competencies
            from weaviate.classes.query import QueryReference
            user_with_refs = user_collection.query.fetch_object_by_id(
                uuid=user_uuid,
                return_references=QueryReference(link_on="has_competencies")
            )

            if user_with_refs.references and 'has_competencies' in user_with_refs.references:
                for comp_obj in user_with_refs.references['has_competencies'].objects:
                    comp_uuid = str(comp_obj.uuid)
                    # Delete the competence
                    competence_collection.data.delete_by_id(comp_uuid)
                    # Remove reference from user
                    user_collection.data.reference_delete(
                        from_uuid=user_uuid,
                        from_property="has_competencies",
                        to=comp_uuid
                    )
                    logger.info("Deleted old competence: %s", comp_uuid)

            # Add new competencies — expects a list of dicts only
            updated_uuids = []
            for comp_dict in competencies_to_insert:
                comp_uuid = HubSpokeIngestion.create_competence(  # type: ignore[assignment]
                    competence_data=comp_dict,
                    user_uuid=user_uuid,
                    apply_sanitization=True,
                    apply_enrichment=True,
                )
                if comp_uuid:
                    updated_uuids.append(comp_uuid)
                    logger.info("Created new competence: %s", comp_uuid)

            logger.info("Updated competencies for user %s: %s new competencies", user_id, len(updated_uuids))
            return {
                "success": True,
                "updated_uuids": updated_uuids,
                "count": len(updated_uuids)
            }

        except Exception as e:
            logger.error("Error updating competencies: %s", e)
            return {"success": False, "error": str(e), "updated_uuids": []}

    @staticmethod
    def delete_competencies_by_user_id(
        user_id: str,
        competencies: str | list[str]
    ) -> dict[str, Any]:
        """
        Delete specific competencies for a user by user_id.
        Matches competencies by title or description pattern.

        Args:
            user_id: The user_id to delete competencies from
            competencies: Single string or list of strings to match against competence titles/descriptions

        Returns:
            Dict with success status and list of deleted competence UUIDs
        """
        try:
            user_collection = get_user_collection()
            competence_collection = get_competence_collection()

            # Find user by user_id
            from weaviate.classes.query import Filter, QueryReference
            result = user_collection.query.fetch_objects(
                filters=Filter.by_property("user_id").equal(user_id),
                limit=1
            )

            if not result.objects:
                logger.error("No user found with user_id: %s", user_id)
                return {"success": False, "error": "User not found", "deleted_uuids": []}

            user_uuid = str(result.objects[0].uuid)
            logger.info("Found user %s for user_id %s", user_uuid, user_id)

            # Get all competencies for this user
            user_with_refs = user_collection.query.fetch_object_by_id(
                uuid=user_uuid,
                return_references=QueryReference(
                    link_on="has_competencies",
                    return_properties=["title", "description", "category"]
                )
            )

            if not user_with_refs.references or 'has_competencies' not in user_with_refs.references:
                logger.info("No competencies found for user %s", user_id)
                return {"success": True, "deleted_uuids": [], "count": 0}

            # Normalize input to list
            if isinstance(competencies, str):
                patterns = [competencies.lower()]
            else:
                patterns = [c.lower() for c in competencies]

            # Find and delete matching competencies
            deleted_uuids = []
            for comp_obj in user_with_refs.references['has_competencies'].objects:
                comp_uuid = str(comp_obj.uuid)
                comp_props = comp_obj.properties
                comp_title = str(comp_props.get('title') or '').lower()
                comp_desc = str(comp_props.get('description') or '').lower()
                comp_category = str(comp_props.get('category') or '').lower()

                # Check if any pattern matches
                for pattern in patterns:
                    if pattern in comp_title or pattern in comp_desc or pattern in comp_category:
                        # Delete the competence
                        competence_collection.data.delete_by_id(comp_uuid)
                        # Remove reference from user
                        user_collection.data.reference_delete(
                            from_uuid=user_uuid,
                            from_property="has_competencies",
                            to=comp_uuid
                        )
                        deleted_uuids.append(comp_uuid)
                        logger.info("Deleted competence: %s (matched pattern: '%s')", comp_uuid, pattern)
                        break  # Only delete once per competence

            logger.info("Deleted %s competencies for user %s", len(deleted_uuids), user_id)
            return {
                "success": True,
                "deleted_uuids": deleted_uuids,
                "count": len(deleted_uuids)
            }

        except Exception as e:
            logger.error("Error deleting competencies: %s", e)
            return {"success": False, "error": str(e), "deleted_uuids": []}

    @staticmethod
    def remove_competence_by_firestore_id(firestore_id: str) -> bool:
        """
        Remove a competence by its Firestore ID.

        Args:
            firestore_id: The Firestore competence_id (e.g., 'competence_12345')

        Returns:
            bool: True if deletion was successful (or if not found, as it's idempotent-ish)
        """
        try:
            collection = get_competence_collection()
            # Find by competence_id
            response = collection.query.fetch_objects(
                filters=Filter.by_property("competence_id").equal(firestore_id),
                limit=1
            )

            if not response.objects:
                logger.info("Competence not found for deletion (already deleted?): %s", firestore_id)
                return True

            uuid = response.objects[0].uuid
            collection.data.delete_by_id(uuid)
            logger.info("Deleted competence %s (UUID: %s)", firestore_id, uuid)
            return True
        except Exception as e:
            logger.error("Error removing competence %s: %s", firestore_id, e)
            # Log error but don't crash main loop if used in bulk
            return False
