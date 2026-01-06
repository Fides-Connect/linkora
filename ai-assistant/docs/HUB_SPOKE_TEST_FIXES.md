# Hub and Spoke Architecture: Test Fixes

## Summary
Fixed all failing tests in the Hub and Spoke architecture implementation by resolving Weaviate v4 API compatibility issues and implementing client-side grouping for reference properties.

## Issues Fixed

### 1. QueryReference API Incompatibility
**Problem**: Weaviate v4 requires `QueryReference` objects for `return_references` parameter, not string lists.

**Error**:
```
WeaviateInvalidInputError: Argument 'return_references' must be one of: 
[<class 'weaviate.collections.classes.grpc._QueryReference'>], but got <class 'str'>
```

**Solution**: Changed from string list to `QueryReference` objects in:
- `hub_spoke_search.py`: All hybrid search calls
- `run_hub_spoke_tests.py`: `fetch_object_by_id()` call

**Before**:
```python
return_references=["owned_by"]
```

**After**:
```python
return_references=QueryReference(
    link_on="owned_by",
    return_properties=["name", "email", "type", "last_active_date"]
)
```

### 2. GroupBy Reference Property Limitation
**Problem**: Weaviate's built-in `GroupBy` doesn't support grouping by reference properties.

**Error**: 
```
Groups: 0  # GroupBy returned 0 groups when trying to group by 'owned_by' reference
```

**Solution**: Implemented client-side grouping in `hub_spoke_search.py`:
1. Fetch more results (`limit * 10`)
2. Track seen profiles in dictionary
3. Keep only best-scoring competence per profile
4. Limit final results to requested count

**Before**:
```python
group_by=GroupBy(
    prop="owned_by",
    number_of_groups=limit,
    objects_per_group=1
)
```

**After**:
```python
# Fetch more results
limit=limit * 10

# Client-side grouping
seen_profiles = {}
for obj in response.objects:
    profile_uuid = extract_profile_uuid(obj)
    if profile_uuid:
        if profile_uuid not in seen_profiles or score_is_better:
            seen_profiles[profile_uuid] = competence

results = list(seen_profiles.values())[:limit]
```

### 3. Import Statement Cleanup
**Problem**: Unused import of `GroupBy` after switching to client-side grouping.

**Solution**: Removed `GroupBy` from imports in `hub_spoke_search.py`.

## Test Results

### All 6 Tests Passing ✓

1. **test_01_bidirectional_link** ✓
   - Verifies Profile → Competence (has_competences)
   - Verifies Competence → Profile (owned_by)

2. **test_02_granularity_match** ✓
   - Tests semantic search with enriched text
   - Finds "Installing Pot Lights" for query "Pot Light Installation"

3. **test_03_spam_filtering** ✓
   - Verifies `sanitize_input()` truncates keyword stuffing
   - Reduces 50-word spam to 5 unique words

4. **test_04_ghost_filtering** ✓
   - Excludes inactive users (>180 days)
   - User C (Ghost) correctly filtered out

5. **test_05_result_grouping** ✓
   - User E (5 competences) appears only once with grouping
   - Client-side grouping by profile works correctly

6. **test_06_helper_functions** ✓
   - `sanitize_input()` working
   - `enrich_text()` working

## Files Modified

1. **src/ai_assistant/hub_spoke_search.py**
   - Changed `return_references` to use `QueryReference` objects (4 locations)
   - Replaced server-side `GroupBy` with client-side grouping logic
   - Removed `GroupBy` import

2. **tests/test_hub_spoke_architecture.py**
   - Added `QueryReference` import
   - Fixed `fetch_object_by_id()` call to use `QueryReference` object

## Running the Tests

```bash
# Run test suite
cd /Users/vc/Codes/fides/ai-assistant
pytest tests/test_hub_spoke_architecture.py -v

# Or run all tests
pytest tests/ -v

# Initialize schema with test data
python scripts/init_hub_spoke_schema.py --load-test-data
```

## Key Learnings

1. **Weaviate v4 Type Safety**: The API is strict about parameter types. Always use proper classes like `QueryReference`, not primitive types.

2. **Reference Property Limitations**: Built-in operations like `GroupBy` don't support reference properties. Use client-side processing when needed.

3. **Hybrid Search Performance**: Client-side grouping requires fetching more results (`limit * 10`) to ensure enough unique profiles after filtering.

4. **Ghost Filtering**: Reference filtering with `Filter.by_ref("owned_by").by_property("last_active_date")` works correctly for excluding inactive users.

## Architecture Benefits Verified

✓ **Bidirectional References**: Both directions work correctly
✓ **Spam Defense**: Sanitization prevents keyword stuffing
✓ **Ghost Filtering**: Inactive users excluded from search
✓ **Granularity Matching**: Enriched text improves semantic search
✓ **Result Grouping**: One result per profile (client-side)
✓ **Hybrid Search**: Vector + keyword search (alpha=0.5)

## Conclusion

The Hub and Spoke architecture is now fully functional and all tests pass. The implementation follows TDD principles and handles all specified edge cases correctly.
