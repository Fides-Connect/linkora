# Hub and Spoke Search Architecture for Service Marketplace

## Overview

This implementation follows **Test-Driven Development (TDD)** to create a "Hub and Spoke" search architecture for a service marketplace using Weaviate Python Client v4.

## Architecture

### The Problem with the Old Design
- Separate `User` and `ServiceProvider` collections
- Skill dilution: A single provider with 10 different skills causes relevance issues
- No defense against SEO spam and keyword stuffing
- Ghost users (inactive accounts) pollute search results
- Multiple listings per provider clutters results

### The Solution: Hub and Spoke

**Hub (UnifiedProfile)**
- Centralized identity for users and companies
- Properties:
  - `name`, `email`, `type` ("user" or "company")
  - `fcm_token`, `created_at`, `has_open_request`
  - `last_active_date` ← Critical for ghost filtering
  - `has_competences` (Reference array)

**Spoke (CompetenceEntry)**
- Granular skills/services with vectorized descriptions
- Properties:
  - `title`, `description` (vectorized for semantic search)
  - `category`, `price_range`
  - `owned_by` (Reference to UnifiedProfile)

**Bidirectional Cross-References**
- Profile → has_competences → [Competence, Competence, ...]
- Competence → owned_by → Profile

## Critical Features

### 1. Skill Dilution Prevention
**Problem:** Searching "Gardening" returns an IT specialist who also does gardening (low relevance).

**Solution:** Search operates on `CompetenceEntry`, not profiles. Each competence is indexed independently with semantic vector search on its description.

### 2. SEO Spam Defense
**Problem:** Malicious users stuff descriptions with keywords: "Plumber Electrician Driver Nurse Teacher..."

**Solution:** `sanitize_input(text, max_unique_words=20)`
- Extracts unique words from input
- Truncates if unique word count exceeds threshold
- Applied during ingestion before vectorization

**Example:**
```python
from src.ai_assistant.hub_spoke_ingestion import sanitize_input

spam = "Plumber Electrician Driver Nurse Teacher " * 10  # 50 words, 5 unique
clean = sanitize_input(spam, max_unique_words=10)
# Returns only first 10 unique words: "plumber electrician driver nurse teacher..."
```

### 3. Ghost User Filtering
**Problem:** Inactive users from years ago appear in search results.

**Solution:** Filter by `owned_by.last_active_date` during search
- `max_inactive_days` parameter (default: 180 days)
- Weaviate cross-reference filtering: `Filter.by_ref("owned_by").by_property("last_active_date").greater_or_equal(cutoff)`

**Example:**
```python
from src.ai_assistant.hub_spoke_search import HubSpokeSearch

results = HubSpokeSearch.search_competences(
    query="Electrician",
    max_inactive_days=180  # Only profiles active in last 180 days
)
```

### 4. Granularity Enrichment
**Problem:** Searching "Electrician" doesn't find someone with skill "Installing Pot Lights".

**Solution:** `enrich_text(text, category)` appends parent category terms
- "Installing Pot Lights" + "Electrical" → "Installing Pot Lights Electrician Electrical Lighting Wiring"
- Improves recall for broad queries while maintaining specific titles

**Enrichment Map:**
```python
{
    "Electrical": ["Electrician", "Electrical", "Lighting", "Wiring", "Power"],
    "Plumbing": ["Plumber", "Plumbing", "Pipes", "Water", "Drain"],
    "Gardening": ["Gardener", "Gardening", "Landscaping", "Plants", "Outdoor"],
    # ... more categories
}
```

### 5. Result Grouping
**Problem:** A user with 5 gardening skills appears 5 times in search results.

**Solution:** Weaviate's `group_by` feature
- Groups results by `owned_by` property
- Returns only the best-matching competence per profile
- `number_of_groups` and `objects_per_group` parameters

**Example:**
```python
results = HubSpokeSearch.search_competences(
    query="Gardening",
    group_by_profile=True  # One result per profile
)
```

## Implementation Files

### Schema & Connection
**File:** `src/ai_assistant/hub_spoke_schema.py`
- `HubSpokeConnection`: Singleton Weaviate client manager
- `init_hub_spoke_schema()`: Creates collections with bidirectional references
- `cleanup_hub_spoke_schema()`: Deletes collections (testing)

**Key Configuration:**
```python
# UnifiedProfile collection
ReferenceProperty(
    name="has_competences",
    target_collection=COMPETENCE_ENTRY_COLLECTION
)

# CompetenceEntry collection with vectorization
vectorizer_config=Configure.Vectorizer.text2vec_model2vec()
Property(
    name="description",
    data_type=DataType.TEXT,
    vectorize_property_name=True,
    skip_vectorization=False
)
```

### Ingestion & Data Processing
**File:** `src/ai_assistant/hub_spoke_ingestion.py`
- `sanitize_input()`: SEO spam defense
- `enrich_text()`: Granularity enhancement
- `HubSpokeIngestion.create_profile_with_competences()`: Batch creation with bidirectional linking

**Critical Linking Logic:**
```python
# Step 1: Create CompetenceEntry with owned_by reference
competence_uuid = competence_collection.data.insert(
    properties={...},
    references={"owned_by": profile_uuid}  # Spoke → Hub
)

# Step 2: Add reverse reference
profile_collection.data.reference_add(
    from_uuid=profile_uuid,
    from_property="has_competences",
    to=competence_uuid  # Hub → Spoke
)
```

### Search & Retrieval
**File:** `src/ai_assistant/hub_spoke_search.py`
- `HubSpokeSearch.search_competences()`: Hybrid search with filtering and grouping
- `HubSpokeSearch.get_profile_competences()`: Get all competences for a profile

**Search Query Structure:**
```python
# Build filter for ghost users
filter_clause = Filter.by_ref("owned_by").by_property("last_active_date").greater_or_equal(cutoff_date)

# Hybrid search with grouping
response = competence_collection.query.hybrid(
    query=query,
    limit=limit,
    filters=filter_clause,
    alpha=0.5,  # Balanced vector + keyword
    return_references=["owned_by"],
    group_by={
        "property": "owned_by",
        "number_of_groups": limit,
        "objects_per_group": 1
    }
)
```

## Test Suite (TDD Approach)

### Test Data
**File:** `tests/test_hub_spoke_data.py`

5 personas covering all edge cases:
1. **User A (The Pro)**: Active, specific skill "Installing Pot Lights"
2. **User B (The Spammer)**: Keyword-stuffed description
3. **User C (The Ghost)**: Perfect match but inactive 365 days
4. **User D (The Generalist)**: Broad "General Electrical Work"
5. **User E (The Enthusiast)**: 5 different gardening skills (grouping test)

### Test Suite
**File:** `tests/test_hub_spoke_architecture.py`

**Test 1: Bidirectional Link**
- Verify `Profile.has_competences` → `Competence`
- Verify `Competence.owned_by` → `Profile`
- Critical for data integrity

**Test 2: Granularity Match**
- Search "Electrician" → should find User A ("Installing Pot Lights")
- Validates `enrich_text()` functionality

**Test 3: Spam Filtering**
- Verify User B's description was sanitized
- Check unique word count ≤ threshold

**Test 4: Ghost Filtering**
- Search "Expert Electrician" with `max_inactive_days=180`
- User C (365 days inactive) should NOT appear

**Test 5: Result Grouping**
- Search "Gardening" with `group_by_profile=True`
- User E should appear ONCE (not 5 times)
- Without grouping, User E appears multiple times

**Test 6: Helper Functions**
- Unit tests for `sanitize_input()` and `enrich_text()`

## Running the Tests

### Prerequisites
```bash
# Install dependencies
pip install weaviate-client

# Start Weaviate locally
docker-compose up -d  # If using Docker

# Or set environment variables for Weaviate Cloud Services
export WEAVIATE_CLUSTER_URL="https://your-cluster.weaviate.network"
export WEAVIATE_API_KEY="your-api-key"
```

### Execute Tests
```bash
cd /path/to/ai-assistant

# Run with pytest
pytest tests/test_hub_spoke_architecture.py -v

# Or run all tests
pytest tests/ -v
```

### Expected Output
```
================================================================================
Hub and Spoke Architecture Test Suite
Following TDD: Tests define requirements, implementation follows
================================================================================

Setting up Hub and Spoke test suite
Loading User A (The Pro)
Loading User B (The Spammer)
Loading User C (The Ghost)
Loading User D (The Generalist)
Loading User E (The Enthusiast)
Waiting 3 seconds for Weaviate indexing...

test_01_bidirectional_link (__main__.TestHubSpokeArchitecture) ... ok
test_02_granularity_match (__main__.TestHubSpokeArchitecture) ... ok
test_03_spam_filtering (__main__.TestHubSpokeArchitecture) ... ok
test_04_ghost_filtering (__main__.TestHubSpokeArchitecture) ... ok
test_05_result_grouping (__main__.TestHubSpokeArchitecture) ... ok
test_06_helper_functions (__main__.TestHubSpokeArchitecture) ... ok

----------------------------------------------------------------------
Ran 6 tests in 5.234s

OK

================================================================================
✓ ALL TESTS PASSED
Hub and Spoke architecture is working correctly!
================================================================================
```

## Usage Examples

### 1. Initialize Schema
```python
from src.ai_assistant.hub_spoke_schema import init_hub_spoke_schema

init_hub_spoke_schema()
```

### 2. Create Profile with Competences
```python
from src.ai_assistant.hub_spoke_ingestion import HubSpokeIngestion

profile_data = {
    "name": "John Electrician",
    "email": "john@example.com",
    "type": "user",
    "has_open_request": False,
    "last_active_date": 5  # 5 days ago
}

competences_data = [
    {
        "title": "Installing Pot Lights",
        "description": "Expert installation of recessed lighting",
        "category": "Electrical",
        "price_range": "$100-$200/hour"
    }
]

result = HubSpokeIngestion.create_profile_with_competences(
    profile_data=profile_data,
    competences_data=competences_data,
    apply_sanitization=True,  # SEO spam defense
    apply_enrichment=True      # Granularity enhancement
)

print(f"Profile UUID: {result['profile_uuid']}")
print(f"Competence UUIDs: {result['competence_uuids']}")
```

### 3. Search for Competences
```python
from src.ai_assistant.hub_spoke_search import HubSpokeSearch

# Search with all protections enabled
results = HubSpokeSearch.search_competences(
    query="Need an electrician for lighting installation",
    limit=10,
    max_inactive_days=180,  # Exclude ghosts
    group_by_profile=True,  # One result per profile
    alpha=0.5               # Balanced hybrid search
)

for result in results:
    profile = result.get('profile', {})
    print(f"Match: {result['title']}")
    print(f"  Provider: {profile['name']}")
    print(f"  Category: {result['category']}")
    print(f"  Price: {result['price_range']}")
    print(f"  Score: {result['score']:.4f}")
    print()
```

### 4. Get All Competences for a Profile
```python
from src.ai_assistant.hub_spoke_search import HubSpokeSearch

competences = HubSpokeSearch.get_profile_competences(profile_uuid)

print(f"Profile has {len(competences)} competence(s):")
for comp in competences:
    print(f"  - {comp['title']} ({comp['category']})")
```

## Benefits of Hub and Spoke

### vs. Old Architecture

| Feature | Old (Separate Collections) | New (Hub and Spoke) |
|---------|---------------------------|---------------------|
| Skill Granularity | Provider-level (all skills lumped) | Competence-level (each skill independent) |
| Search Precision | Low (skill dilution) | High (targeted vector search) |
| Spam Defense | None | Sanitization at ingestion |
| Ghost Filtering | Manual post-processing | Built-in with cross-ref filters |
| Result Deduplication | Manual grouping | Native `group_by` support |
| Bidirectional Links | None | Full referential integrity |

### Performance
- **Vector Search**: O(log n) with HNSW index
- **Cross-Reference Filtering**: Efficient with Weaviate's graph structure
- **Grouping**: Native support, no post-processing needed
- **Scalability**: Handles millions of competences across thousands of profiles

### Data Integrity
- Bidirectional references enforce consistency
- Orphaned competences prevented by `owned_by` requirement
- Profile deletion can cascade to competences (configurable)

## Future Enhancements

1. **Dynamic Enrichment**: ML-based category term expansion
2. **Reputation Scoring**: Integrate ratings into search ranking
3. **Geo-Filtering**: Add location-based filtering
4. **Multi-Language**: Support for multilingual descriptions
5. **A/B Testing**: Compare different alpha values for hybrid search

## Conclusion

This Hub and Spoke architecture provides:
- ✓ Granular, precise skill matching
- ✓ Robust spam defense
- ✓ Active user prioritization
- ✓ Clean, grouped results
- ✓ Bidirectional data integrity

All backed by comprehensive TDD tests covering real-world edge cases.
