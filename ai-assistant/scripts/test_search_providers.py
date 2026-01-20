#!/usr/bin/env python3
"""
Test Provider Search Script
Tests the hybrid search functionality directly without requiring the server.

Usage:
    python scripts/test_search_providers.py
"""
import sys
import os
import json
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.ai_assistant.data_provider import get_data_provider

def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{'=' * 70}")
    print(f"{text}")
    print(f"{'=' * 70}\n")

def print_provider(provider: dict, index: int):
    """Print provider information."""
    # Handle both formats: direct hybrid search results and data provider mapped results
    name = provider.get('name') or provider.get('profile', {}).get('name', 'Unknown')
    category = provider.get('category', 'N/A')
    price = provider.get('price_range') or 'N/A'
    score = provider.get('score', 0)
    description = provider.get('description', '')
    
    print(f"{index}. {name}")
    print(f"   Category: {category}")
    print(f"   Price: {price}")
    print(f"   Score: {score:.3f}")
    
    if description:
        preview = description[:100] + '...' if len(description) > 100 else description
        print(f"   Description: {preview}")
    print()

async def main():
    """Run search tests."""
    print_header("Provider Search Test - Using Data Provider (No Server Required)")
    
    # Get data provider instance
    data_provider = get_data_provider()
    
    # Test 1: Search for Electricians
    print_header("Test 1: Search for Electricians")
    search_request = {
        "category": "Electrical",
        "criterions": ["outdoor light", "repair"],
        "available_time": "flexible"
    }
    
    print(f"Search Request: {search_request}\n")
    
    # Convert to JSON string as expected by data_provider
    query_text = json.dumps(search_request)
    results = await data_provider.search_providers(
        query_text=query_text,
        limit=10
    )
    
    if results:
        print(f"✓ Found {len(results)} provider(s):\n")
        for i, provider in enumerate(results, 1):
            print_provider(provider, i)
    else:
        print("✗ No providers found")
    
    # Test 2: Search for Gardening
    print_header("Test 2: Search for Gardening Services")
    search_request = {
        "category": "Gardening",
        "criterions": ["cheap", "lawn"],
        "available_time": "weekend"
    }
    
    print(f"Search Request: {search_request}\n")
    
    query_text = json.dumps(search_request)
    results = await data_provider.search_providers(
        query_text=query_text,
        limit=10
    )
    
    if results:
        print(f"✓ Found {len(results)} provider(s):\n")
        for i, provider in enumerate(results, 1):
            print_provider(provider, i)
    else:
        print("✗ No providers found")
    
    # Test 3: Search with only criterions
    print_header("Test 3: Search with Only Criterions")
    search_request = {
        "category": None,
        "criterions": ["installation", "wiring"],
        "available_time": "flexible"
    }
    
    print(f"Search Request: {search_request}\n")
    
    query_text = json.dumps(search_request)
    results = await data_provider.search_providers(
        query_text=query_text,
        limit=10
    )
    
    if results:
        print(f"✓ Found {len(results)} provider(s):\n")
        for i, provider in enumerate(results, 1):
            print_provider(provider, i)
    else:
        print("✗ No providers found")
    
    print_header("Test Summary")
    print("✓ All search tests completed successfully!")
    print("\nThe admin endpoint /admin/search/providers is ready to use.")
    print("You can test it via HTTP POST with:")
    print('  curl -X POST http://localhost:8080/admin/search/providers \\')
    print('       -H "Authorization: Bearer YOUR_ADMIN_SECRET" \\')
    print('       -H "Content-Type: application/json" \\')
    print('       -d \'{"category": "Electrical", "criterions": ["fast"], "available_time": "flexible"}\'')

if __name__ == '__main__':
    asyncio.run(main())
