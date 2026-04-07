"""
Hub and Spoke Search Architecture for Service Marketplace
==========================================================

Architecture:
- Hub (User): Identity model for users/companies
- Spoke (Competence): Specific skills/services with descriptions
- Bidirectional Cross-References: User ↔ Competence

"""
import os
import logging
from typing import Any, TypeAlias
import weaviate
from weaviate.classes.config import Configure, Property, DataType, ReferenceProperty
from weaviate.auth import AuthApiKey
from weaviate.collections.collection.sync import Collection

logger = logging.getLogger(__name__)

# Collection names
USER_COLLECTION = "User"
COMPETENCE_COLLECTION = "Competence"
# Lite-mode ephemeral collection — multi-tenant; one tenant per search, deleted after the search.
LITE_COMPETENCE_COLLECTION = "LiteCompetence"
WeaviateCollection: TypeAlias = Collection[Any, Any]

class HubSpokeConnection:
    """Singleton connection manager for Hub and Spoke architecture."""

    _client: weaviate.WeaviateClient | None = None

    @classmethod
    def get_client(cls) -> weaviate.WeaviateClient:
        """Get or create Weaviate client."""
        if cls._client is None:
            cluster_url = os.getenv('WEAVIATE_CLUSTER_URL')
            api_key = os.getenv('WEAVIATE_API_KEY')

            try:
                if cluster_url and api_key:
                    logger.info("Connecting to Weaviate Cloud Services at %s", cluster_url)
                    cls._client = weaviate.connect_to_wcs(
                        cluster_url=cluster_url,
                        auth_credentials=AuthApiKey(api_key),
                    )
                else:
                    weaviate_url = os.getenv('WEAVIATE_URL', 'http://localhost:8090')
                    logger.info("Connecting to local Weaviate at %s", weaviate_url)

                    url_parts = weaviate_url.replace('http://', '').replace('https://', '')
                    host = url_parts.split(':')[0]
                    port = int(url_parts.split(':')[-1].split('/')[0]) if ':' in url_parts else 8080
                    is_https = weaviate_url.startswith('https')

                    cls._client = weaviate.connect_to_custom(
                        http_host=host,
                        http_port=port,
                        http_secure=is_https,
                        grpc_host=host,
                        grpc_port=50051,
                        grpc_secure=is_https
                    )

                if not cls._client.is_ready():
                    raise ConnectionError("Weaviate is not ready")

                logger.info("Successfully connected to Weaviate")

            except Exception as e:
                logger.error("Failed to connect to Weaviate: %s", e)
                raise

        return cls._client

    @classmethod
    def close(cls) -> None:
        """Close Weaviate connection."""
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            logger.info("Weaviate connection closed")


def init_hub_spoke_schema() -> bool | None:
    """
    Initialize Hub and Spoke schema with bidirectional cross-references.

    Collections:
    1. Competence (Spoke) - Created FIRST
    2. User (Hub) - Created SECOND with reference to Competence
    3. Add owned_by reference to Competence after User exists

    Note: Weaviate v4 Python client handles cross-references at data insertion time,
    but we define the schema properties for explicit structure.
    """
    try:
        client = HubSpokeConnection.get_client()

        # Step 1: Create Competence FIRST (without owned_by reference initially)
        if not client.collections.exists(COMPETENCE_COLLECTION):
            try:
                client.collections.create(
                    name=COMPETENCE_COLLECTION,
                    vector_config=Configure.Vectors.text2vec_model2vec(),  # type: ignore[attr-defined]
                    properties=[
                        Property(name="competence_id", data_type=DataType.TEXT,
                                 skip_vectorization=True),  # Link to Firestore ID
                        Property(name="title", data_type=DataType.TEXT,
                                 skip_vectorization=True, index_searchable=True),
                        # Raw description — stored for display only, NOT vectorized.
                        # Vector search is driven by search_optimized_summary instead.
                        Property(
                            name="description",
                            data_type=DataType.TEXT,
                            skip_vectorization=True,
                            index_searchable=True,
                        ),
                        # ── Filter / rank properties ─────────────────────────────────
                        Property(name="category", data_type=DataType.TEXT,
                                 skip_vectorization=True, index_searchable=True),
                        Property(name="year_of_experience", data_type=DataType.INT,
                                 skip_vectorization=True),
                        Property(name="price_per_hour", data_type=DataType.NUMBER,
                                 skip_vectorization=True),
                        # availability_tags: normalised tokens, e.g. ["weekend","monday","morning"]
                        # Used for ContainsAny where-filters in search_providers.
                        Property(name="availability_tags", data_type=DataType.TEXT_ARRAY,
                                 skip_vectorization=True),
                        # availability_text: human-readable string stored for display (Firestore
                        # is authoritative, but kept here so result objects are self-contained).
                        Property(name="availability_text", data_type=DataType.TEXT,
                                 skip_vectorization=True, index_searchable=True),
                        # ── Primary vector source ────────────────────────────────────
                        # LLM-rewritten summary, optimised for semantic search.
                        # This is the ONLY vectorized field — all nearText queries target it.
                        Property(
                            name="search_optimized_summary",
                            data_type=DataType.TEXT,
                            vectorize_property_name=True,
                            skip_vectorization=False,
                        ),
                        # primary_type: Google Places primaryTypeDisplayName (e.g. "Wedding
                        # Photographer"). Vectorized so nearText queries benefit; also
                        # BM25-searchable for exact-type keyword matching.
                        Property(
                            name="primary_type",
                            data_type=DataType.TEXT,
                            skip_vectorization=False,
                            index_searchable=True,
                        ),
                        # skills_list: explicit + implicit skills, stored for retrieval.
                        # NOT vectorized individually — the summary already captures them.
                        Property(name="skills_list", data_type=DataType.TEXT_ARRAY,
                                 skip_vectorization=True),
                        # review_snippets: positive review sentences from Google Places.
                        # Stored for card reasoning display — NOT vectorized.
                        Property(name="review_snippets", data_type=DataType.TEXT_ARRAY,
                                 skip_vectorization=True),
                    ],
                )
                logger.info("Created collection with vectorization: %s", COMPETENCE_COLLECTION)
            except weaviate.exceptions.ObjectAlreadyExistsError:
                logger.warning("Collection %s already exists — skipping creation", COMPETENCE_COLLECTION)
        else:
            logger.info("Collection already exists: %s", COMPETENCE_COLLECTION)

        # Step 2: Create User SECOND (now it can reference existing Competence)
        if not client.collections.exists(USER_COLLECTION):
            try:
                client.collections.create(
                    name=USER_COLLECTION,
                    # index_null_state=True is required for is_none() filter on last_sign_in.
                    # This enables null-safe ghost filtering so providers who were created
                    # before last_sign_in was tracked are not silently excluded from searches.
                    inverted_index_config=Configure.inverted_index(index_null_state=True),
                    properties=[
                        Property(name="user_id", data_type=DataType.TEXT),  # External ID (e.g. Firebase UID)
                        Property(name="name", data_type=DataType.TEXT),
                        Property(name="email", data_type=DataType.TEXT),
                        Property(name="location", data_type=DataType.TEXT),
                        Property(name="self_introduction", data_type=DataType.TEXT),
                        Property(name="is_service_provider", data_type=DataType.BOOL),  # True if user offers services
                        Property(name="photo_url", data_type=DataType.TEXT),
                        Property(name="fcm_token", data_type=DataType.TEXT),
                        Property(name="created_at", data_type=DataType.DATE),
                        Property(name="last_sign_in", data_type=DataType.DATE),
                        Property(name="has_open_request", data_type=DataType.BOOL),
                        Property(name="feedback_positive", data_type=DataType.TEXT_ARRAY),
                        Property(name="feedback_negative", data_type=DataType.TEXT_ARRAY),
                        Property(name="average_rating", data_type=DataType.NUMBER),
                        Property(name="review_count", data_type=DataType.INT),
                        Property(name="rating_count", data_type=DataType.INT, skip_vectorization=True),
                        # External-source metadata (Google Places integration)
                        Property(name="source", data_type=DataType.TEXT, skip_vectorization=True),
                        Property(name="phone", data_type=DataType.TEXT, skip_vectorization=True),
                        Property(name="website", data_type=DataType.TEXT, skip_vectorization=True),
                        Property(name="address", data_type=DataType.TEXT, skip_vectorization=True),
                    ],
                    references=[
                        ReferenceProperty(
                            name="has_competencies",
                            target_collection=COMPETENCE_COLLECTION
                        )
                    ]
                )
                logger.info("Created collection: %s", USER_COLLECTION)
            except weaviate.exceptions.ObjectAlreadyExistsError:
                logger.warning("Collection %s already exists — skipping creation", USER_COLLECTION)
        else:
            logger.info("Collection already exists: %s", USER_COLLECTION)

        # Step 3: Add owned_by reference to Competence (now that User exists)
        # Update the collection to add the cross-reference
        competence_collection = client.collections.get(COMPETENCE_COLLECTION)
        config = competence_collection.config.get()

        # Check if owned_by reference already exists
        has_owned_by = any(ref.name == "owned_by" for ref in (config.references or []))

        if not has_owned_by:
            try:
                competence_collection.config.add_reference(
                    ref=ReferenceProperty(
                        name="owned_by",
                        target_collection=USER_COLLECTION
                    )
                )
                logger.info("Added 'owned_by' reference to %s", COMPETENCE_COLLECTION)
            except weaviate.exceptions.ObjectAlreadyExistsError:
                logger.warning("'owned_by' reference in %s already exists — skipping", COMPETENCE_COLLECTION)
        else:
            logger.info("'owned_by' reference already exists in %s", COMPETENCE_COLLECTION)

        # Step 4: Add new User properties if they don't exist yet (migration guard)
        _new_user_properties = [
            ("source", DataType.TEXT, True),
            ("phone", DataType.TEXT, True),
            ("website", DataType.TEXT, True),
            ("address", DataType.TEXT, True),
            ("opening_hours", DataType.TEXT, True),
            ("maps_url", DataType.TEXT, True),
            ("rating_count", DataType.INT, True),
        ]
        user_collection = client.collections.get(USER_COLLECTION)
        user_config = user_collection.config.get()
        existing_prop_names = {p.name for p in (user_config.properties or [])}
        for prop_name, prop_dtype, skip_vec in _new_user_properties:
            if prop_name not in existing_prop_names:
                try:
                    user_collection.config.add_property(
                        Property(name=prop_name, data_type=prop_dtype, skip_vectorization=skip_vec)
                    )
                    logger.info("Added '%s' property to %s", prop_name, USER_COLLECTION)
                except weaviate.exceptions.ObjectAlreadyExistsError:
                    logger.warning("'%s' property in %s already exists — skipping", prop_name, USER_COLLECTION)

        # Step 5: Add new Competence properties if they don't exist yet (migration guard)
        # review_snippets: positive review sentences stored for card reasoning display.
        # NOT vectorized — the search_optimized_summary already captures review context.
        _new_competence_properties = [
            ("review_snippets", DataType.TEXT_ARRAY, True),
            # primary_type: GP primaryTypeDisplayName — vectorized for richer semantic matching.
            ("primary_type", DataType.TEXT, False),
        ]
        competence_config = competence_collection.config.get()
        existing_comp_prop_names = {p.name for p in (competence_config.properties or [])}
        for prop_name, prop_dtype, skip_vec in _new_competence_properties:
            if prop_name not in existing_comp_prop_names:
                try:
                    competence_collection.config.add_property(
                        Property(name=prop_name, data_type=prop_dtype, skip_vectorization=skip_vec)
                    )
                    logger.info("Added '%s' property to %s", prop_name, COMPETENCE_COLLECTION)
                except weaviate.exceptions.ObjectAlreadyExistsError:
                    logger.warning("'%s' property in %s already exists — skipping", prop_name, COMPETENCE_COLLECTION)

        logger.info("Hub and Spoke schema initialization complete")
        return True

    except Exception as e:
        logger.error("Error initializing Hub and Spoke schema: %s", e)
        raise


def get_user_collection() -> WeaviateCollection:
    """Get User collection, auto-initialising schema if needed."""
    client = HubSpokeConnection.get_client()
    if not client.collections.exists(USER_COLLECTION):
        logger.warning("User collection missing — auto-initialising Hub and Spoke schema")
        init_hub_spoke_schema()
    return client.collections.get(USER_COLLECTION)


def get_competence_collection() -> WeaviateCollection:
    """Get Competence collection, auto-initialising schema if needed."""
    client = HubSpokeConnection.get_client()
    if not client.collections.exists(COMPETENCE_COLLECTION):
        logger.warning("Competence collection missing — auto-initialising Hub and Spoke schema")
        init_hub_spoke_schema()
    return client.collections.get(COMPETENCE_COLLECTION)


def cleanup_hub_spoke_schema() -> bool | None:
    """Delete collections (for testing purposes)."""
    try:
        client = HubSpokeConnection.get_client()

        if client.collections.exists(COMPETENCE_COLLECTION):
            client.collections.delete(COMPETENCE_COLLECTION)
            logger.info("Deleted collection: %s", COMPETENCE_COLLECTION)

        if client.collections.exists(USER_COLLECTION):
            client.collections.delete(USER_COLLECTION)
            logger.info("Deleted collection: %s", USER_COLLECTION)

        logger.info("Hub and Spoke schema cleanup complete")
        return True

    except Exception as e:
        logger.error("Error cleaning up Hub and Spoke schema: %s", e)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Lite-mode multi-tenant helpers
# ─────────────────────────────────────────────────────────────────────────────

def init_lite_schema() -> bool | None:
    """Create the ``LiteCompetence`` collection with multi-tenancy enabled.

    Safe to call multiple times — skips creation when the collection already
    exists.  Multi-tenancy is a collection-level flag that must be set at
    creation time and cannot be added later.

    The collection is flat (no cross-references) so that per-search tenants
    can be created and deleted atomically without any cascade concerns.
    """
    try:
        client = HubSpokeConnection.get_client()

        if client.collections.exists(LITE_COMPETENCE_COLLECTION):
            logger.info("Collection already exists: %s", LITE_COMPETENCE_COLLECTION)
            return True

        client.collections.create(
            name=LITE_COMPETENCE_COLLECTION,
            multi_tenancy_config=Configure.multi_tenancy(enabled=True),
            vector_config=Configure.Vectors.text2vec_model2vec(),  # type: ignore[attr-defined]
            properties=[
                # ── Display fields ───────────────────────────────────────────
                Property(name="name", data_type=DataType.TEXT,
                         skip_vectorization=True, index_searchable=True),
                Property(name="title", data_type=DataType.TEXT,
                         skip_vectorization=True, index_searchable=True),
                Property(name="description", data_type=DataType.TEXT,
                         skip_vectorization=True, index_searchable=True),
                # ── Primary vector source (English) ──────────────────────────
                Property(name="search_optimized_summary", data_type=DataType.TEXT,
                         vectorize_property_name=True, skip_vectorization=False),
                # ── Keyword-searchable category fields ───────────────────────
                Property(name="primary_type", data_type=DataType.TEXT,
                         skip_vectorization=False, index_searchable=True),
                Property(name="category", data_type=DataType.TEXT,
                         skip_vectorization=True, index_searchable=True),
                # ── Contact / location (skip vectorization) ──────────────────
                Property(name="phone", data_type=DataType.TEXT, skip_vectorization=True),
                Property(name="website", data_type=DataType.TEXT, skip_vectorization=True),
                Property(name="address", data_type=DataType.TEXT, skip_vectorization=True),
                Property(name="opening_hours", data_type=DataType.TEXT, skip_vectorization=True),
                Property(name="maps_url", data_type=DataType.TEXT, skip_vectorization=True),
                # ── Rating ───────────────────────────────────────────────────
                Property(name="average_rating", data_type=DataType.NUMBER, skip_vectorization=True),
                Property(name="rating_count", data_type=DataType.INT, skip_vectorization=True),
                # ── Media / reviews ──────────────────────────────────────────
                Property(name="photo_url", data_type=DataType.TEXT, skip_vectorization=True),
                Property(name="review_snippets", data_type=DataType.TEXT_ARRAY,
                         skip_vectorization=True),
                Property(name="skills_list", data_type=DataType.TEXT_ARRAY,
                         skip_vectorization=True),
                # ── Source tracking ──────────────────────────────────────────
                Property(name="place_id", data_type=DataType.TEXT, skip_vectorization=True),
                Property(name="webpage_crawled", data_type=DataType.BOOL, skip_vectorization=True),
                Property(name="email", data_type=DataType.TEXT, skip_vectorization=True),
            ],
        )
        logger.info("Created multi-tenant collection: %s", LITE_COMPETENCE_COLLECTION)
        return True

    except weaviate.exceptions.ObjectAlreadyExistsError:
        logger.info("Collection already exists (race): %s", LITE_COMPETENCE_COLLECTION)
        return True
    except Exception as exc:
        logger.error("Error initialising %s schema: %s", LITE_COMPETENCE_COLLECTION, exc)
        raise


def get_lite_competence_collection() -> WeaviateCollection:
    """Return the ``LiteCompetence`` collection, ensuring the schema exists."""
    client = HubSpokeConnection.get_client()
    if not client.collections.exists(LITE_COMPETENCE_COLLECTION):
        logger.warning("%s collection missing — auto-initialising", LITE_COMPETENCE_COLLECTION)
        init_lite_schema()
    return client.collections.get(LITE_COMPETENCE_COLLECTION)


def cleanup_orphaned_lite_tenants() -> None:
    """Delete all tenants in ``LiteCompetence`` on server startup.

    All tenants in this collection are ephemeral — one per search, deleted
    after the search completes.  Any tenants present at startup are orphans
    from a previous process that crashed before cleanup.  Removing them is
    safe and prevents unbounded accumulation.

    Logs a warning and returns silently if Weaviate is unreachable or the
    collection does not exist yet (e.g. first run).
    """
    try:
        client = HubSpokeConnection.get_client()
        if not client.collections.exists(LITE_COMPETENCE_COLLECTION):
            logger.info("Startup: %s collection not yet created — skipping orphan cleanup",
                        LITE_COMPETENCE_COLLECTION)
            return
        lite_col = client.collections.get(LITE_COMPETENCE_COLLECTION)
        tenants = lite_col.tenants.get()
        if tenants:
            tenant_names = list(tenants.keys())
            lite_col.tenants.remove(tenant_names)
            logger.info("Startup: removed %d orphaned lite tenant(s): %s",
                        len(tenant_names), tenant_names)
        else:
            logger.info("Startup: no orphaned lite tenants found")
    except Exception as exc:
        logger.warning("Startup: lite tenant cleanup failed (non-fatal): %s", exc)
