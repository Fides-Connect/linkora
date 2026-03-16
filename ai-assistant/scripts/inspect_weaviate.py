#!/usr/bin/env python3
"""
Diagnostic: inspect current state of Weaviate DB.
Usage: python scripts/inspect_weaviate.py [--user-id <firebase_uid>]
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ai_assistant.hub_spoke_schema import get_user_collection, get_competence_collection, HubSpokeConnection
from weaviate.classes.query import QueryReference, Filter, MetadataQuery


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", default=None)
    args = parser.parse_args()

    client = HubSpokeConnection.get_client()

    # 1. Schema config
    print("\n" + "="*70)
    print("1. USER COLLECTION — inverted_index_config")
    print("="*70)
    uc = client.collections.get("User")
    cfg = uc.config.get()
    iic = cfg.inverted_index_config
    print(f"  index_null_state    : {getattr(iic, 'index_null_state', 'N/A')}")
    print(f"  index_timestamps    : {getattr(iic, 'index_timestamps', 'N/A')}")
    print(f"  index_property_length: {getattr(iic, 'index_property_length', 'N/A')}")

    # 2. All users
    print("\n" + "="*70)
    print("2. ALL USERS")
    print("="*70)
    user_coll = get_user_collection()
    filters = Filter.by_property("user_id").equal(args.user_id) if args.user_id else None
    resp = user_coll.query.fetch_objects(
        limit=50,
        filters=filters,
        return_references=QueryReference(link_on="has_competencies", return_properties=["title"]),
    )
    if not resp.objects:
        print("  *** NO USERS FOUND ***")
    for obj in resp.objects:
        p = obj.properties
        comps = []
        if obj.references and "has_competencies" in obj.references:
            comps = [c.properties.get("title") for c in obj.references["has_competencies"].objects]
        print(f"  uuid={obj.uuid}")
        print(f"    user_id             = {p.get('user_id')}")
        print(f"    name                = {p.get('name')}")
        print(f"    is_service_provider = {p.get('is_service_provider')}")
        print(f"    last_sign_in        = {p.get('last_sign_in')}")
        print(f"    competencies ({len(comps)})   = {comps}")
        print()

    # 3. All competencies
    print("\n" + "="*70)
    print("3. ALL COMPETENCIES")
    print("="*70)
    comp_coll = get_competence_collection()
    resp = comp_coll.query.fetch_objects(
        limit=100,
        return_references=QueryReference(
            link_on="owned_by",
            return_properties=["user_id", "name", "is_service_provider", "last_sign_in"],
        ),
    )
    print(f"  Total competencies in collection: {len(resp.objects)}")
    if not resp.objects:
        print("  *** EMPTY — no competencies ingested ***")
    for obj in resp.objects:
        p = obj.properties
        u = {}
        if obj.references and "owned_by" in obj.references and obj.references["owned_by"].objects:
            u = obj.references["owned_by"].objects[0].properties
        print(f"  uuid={obj.uuid}")
        print(f"    title              = {p.get('title')!r}")
        print(f"    category           = {p.get('category')!r}")
        print(f"    competence_id      = {p.get('competence_id')!r}")
        print(f"    availability_tags  = {p.get('availability_tags', [])}")
        print(f"    search_opt_summary = {str(p.get('search_optimized_summary',''))[:60]!r}")
        print(f"    owned_by.user_id   = {u.get('user_id')}")
        print(f"    owned_by.name      = {u.get('name')}")
        print(f"    owned_by.is_sp     = {u.get('is_service_provider')}")
        print(f"    owned_by.last_sign_in = {u.get('last_sign_in')}")
        print()

    # 4. Hybrid search without any filter
    print("\n" + "="*70)
    print("4. HYBRID SEARCH 'Flutter developer' — NO FILTER")
    print("="*70)
    resp = comp_coll.query.hybrid(
        query="Flutter developer mobile app",
        limit=5,
        alpha=0.5,
        return_metadata=MetadataQuery(score=True),
        return_references=QueryReference(
            link_on="owned_by",
            return_properties=["user_id", "name", "is_service_provider", "last_sign_in"],
        ),
    )
    if not resp.objects:
        print("  *** 0 results without any filter — vector index may be empty ***")
    for obj in resp.objects:
        u = {}
        if obj.references and "owned_by" in obj.references and obj.references["owned_by"].objects:
            u = obj.references["owned_by"].objects[0].properties
        score = obj.metadata.score if obj.metadata else 0
        print(f"  score={score:.4f}  title={obj.properties.get('title')!r}  is_sp={u.get('is_service_provider')}  last_sign_in={u.get('last_sign_in')}")

    # 5. Filter only: is_service_provider=True
    print("\n" + "="*70)
    print("5. FETCH OBJECTS — filter: is_service_provider=True only")
    print("="*70)
    resp = comp_coll.query.fetch_objects(
        limit=10,
        filters=Filter.by_ref("owned_by").by_property("is_service_provider").equal(True),
        return_references=QueryReference(
            link_on="owned_by",
            return_properties=["user_id", "name", "is_service_provider", "last_sign_in"],
        ),
    )
    print(f"  Results: {len(resp.objects)}")
    for obj in resp.objects:
        u = {}
        if obj.references and "owned_by" in obj.references and obj.references["owned_by"].objects:
            u = obj.references["owned_by"].objects[0].properties
        print(f"  title={obj.properties.get('title')!r}  is_sp={u.get('is_service_provider')}  last_sign_in={u.get('last_sign_in')}")

    print("\nDone.")


if __name__ == "__main__":
    main()
