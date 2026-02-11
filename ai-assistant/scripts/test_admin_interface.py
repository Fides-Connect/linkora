#!/usr/bin/env python3
"""
Admin Interface Test Script
Tests all admin endpoints to ensure they're working correctly.

Usage:
    python scripts/test_admin_interface.py
    
Set ADMIN_SECRET_KEY environment variable before running:
    export ADMIN_SECRET_KEY='your_admin_secret_key'
"""
import os
import sys
import asyncio
import aiohttp
from typing import Dict, Any

BASE_URL = os.getenv('ADMIN_BASE_URL', 'http://localhost:8080')
ADMIN_SECRET_KEY = os.getenv('ADMIN_SECRET_KEY')

class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.RESET}\n")

def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}✗ {text}{Colors.RESET}")

def print_warning(text: str):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

def print_result(response: Dict[Any, Any]):
    """Print formatted JSON response."""
    import json
    print(json.dumps(response, indent=2))


# TODO: add remove user endpoint and remove skills endpoint 

async def test_endpoint(
    session: aiohttp.ClientSession,
    method: str,
    path: str,
    data: Dict = None,
    expected_status: int = 200
) -> Dict[str, Any]:
    """
    Test an admin endpoint.
    
    Returns:
        Dict with 'success', 'status', and 'data' keys
    """
    url = f"{BASE_URL}{path}"
    headers = {'Authorization': f'Bearer {ADMIN_SECRET_KEY}'}
    
    try:
        if method == 'GET':
            async with session.get(url, headers=headers) as response:
                status = response.status
                try:
                    data = await response.json()
                except:
                    data = {"text": await response.text()}
        elif method == 'POST':
            headers['Content-Type'] = 'application/json'
            async with session.post(url, headers=headers, json=data) as response:
                status = response.status
                try:
                    data = await response.json()
                except:
                    data = {"text": await response.text()}
        
        success = status == expected_status
        return {
            'success': success,
            'status': status,
            'data': data
        }
    except Exception as e:
        return {
            'success': False,
            'status': 0,
            'error': str(e)
        }

async def run_tests():
    """Run all admin interface tests."""
    if not ADMIN_SECRET_KEY:
        print_error("ADMIN_SECRET_KEY environment variable not set!")
        print("Set it with: export ADMIN_SECRET_KEY='your_admin_secret_key'")
        sys.exit(1)
    
    print_header("Admin Interface Test Suite")
    print(f"Base URL: {BASE_URL}")
    print(f"Secret Key: {ADMIN_SECRET_KEY[:10]}...{ADMIN_SECRET_KEY[-5:]}\n")
    
    async with aiohttp.ClientSession() as session:
        # Test 1: Health Check
        print_header("Test 1: Admin Health Check")
        result = await test_endpoint(session, 'GET', '/admin/health')
        if result['success']:
            print_success("Admin health endpoint accessible")
            print_result(result['data'])
        else:
            print_error(f"Health check failed: {result.get('error', 'Unknown error')}")
        
        # Test 2: Statistics
        print_header("Test 2: System Statistics")
        result = await test_endpoint(session, 'GET', '/admin/stats')
        if result['success']:
            print_success("Statistics retrieved successfully")
            print_result(result['data'])
        else:
            print_error(f"Stats failed: {result.get('error', 'Unknown error')}")
        
        # Test 3: List Users
        print_header("Test 3: List Users")
        result = await test_endpoint(session, 'GET', '/admin/users?limit=5')
        if result['success']:
            print_success(f"Retrieved {result['data'].get('count', 0)} users")
            print_result(result['data'])
        else:
            error_msg = result.get('error', 'Unknown error')
            print_error(f"List users failed: {error_msg}")
            if 'data' in result:
                print(f"Response data: {result['data']}")
        
        # Test 4: List Competencies (Spokes)
        print_header("Test 4: List Competencies (Spokes)")
        result = await test_endpoint(session, 'GET', '/admin/competencies?limit=5')
        if result['success']:
            print_success(f"Retrieved {result['data'].get('count', 0)} competencies")
            print_result(result['data'])
        else:
            error_msg = result.get('error', 'Unknown error')
            print_error(f"List competencies failed: {error_msg}")
            if 'data' in result:
                print(f"Response data: {result['data']}")
        
        # Test 4b: Search Providers
        print_header("Test 4b: Search Providers")
        search_payload = {
            "category": "Electrical",
            "criterions": ["fast"],
            "available_time": "flexible"
        }
        result = await test_endpoint(session, 'POST', '/admin/search/providers', data=search_payload)
        if result['success']:
             print_success(f"Search found {result['data'].get('count', 0)} providers")
             print_result(result['data'])
        else:
             print_error(f"Search providers failed: {result.get('error', 'Unknown error')}")
        
        # Test 5: Unauthorized Access (should fail)
        print_header("Test 5: Unauthorized Access (Expected to Fail)")
        headers_no_auth = {}
        try:
            async with session.get(f"{BASE_URL}/admin/health", headers=headers_no_auth) as response:
                if response.status == 401:
                    print_success("Unauthorized access correctly rejected")
                else:
                    print_error(f"Unexpected status: {response.status}")
        except Exception as e:
            print_error(f"Error testing unauthorized access: {e}")
        
        # Test 6: Test Notification (only if FCM token provided)
        fcm_token = os.getenv('TEST_FCM_TOKEN')
        if fcm_token:
            print_header("Test 6: Test Notification")
            result = await test_endpoint(
                session,
                'POST',
                '/admin/notifications/test',
                data={
                    'fcm_token': fcm_token,
                    'title': 'Admin Interface Test',
                    'body': 'This is a test notification from the admin interface'
                }
            )
            if result['success']:
                print_success("Test notification sent")
                print_result(result['data'])
            else:
                print_error(f"Test notification failed: {result.get('error', 'Unknown error')}")
        else:
            print_warning("Skipping notification test (TEST_FCM_TOKEN not set)")
        
        print_header("Test Summary")
        print_success("Admin interface tests completed!")
        print("\nTo test notifications, set TEST_FCM_TOKEN environment variable:")
        print("  export TEST_FCM_TOKEN='your_device_fcm_token'")

if __name__ == '__main__':
    asyncio.run(run_tests())
