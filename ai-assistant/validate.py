#!/usr/bin/env python3
"""
Validation script for AI Assistant configuration
Run this before starting the container to check your setup.
"""
import os
import sys
import json
from pathlib import Path


def print_status(message, status):
    """Print colored status message."""
    colors = {
        'ok': '\033[92m✓\033[0m',
        'error': '\033[91m✗\033[0m',
        'warning': '\033[93m⚠\033[0m',
        'info': '\033[94mℹ\033[0m'
    }
    print(f"{colors.get(status, '')} {message}")


def check_env_file():
    """Check if .env file exists and is configured."""
    print("\n1. Checking environment file...")
    
    if not Path('.env').exists():
        print_status(".env file not found", 'error')
        print_status("Run: cp .env.template .env", 'info')
        return False
    
    print_status(".env file exists", 'ok')
    
    # Load and check variables
    with open('.env') as f:
        env_vars = {}
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    
    required_vars = ['GOOGLE_APPLICATION_CREDENTIALS', 'GEMINI_API_KEY']
    all_ok = True
    
    for var in required_vars:
        if var not in env_vars:
            print_status(f"{var} not set in .env", 'error')
            all_ok = False
        elif not env_vars[var] or 'your_' in env_vars[var].lower():
            print_status(f"{var} not configured (still has placeholder)", 'error')
            all_ok = False
        else:
            # Mask sensitive values
            masked = env_vars[var][:10] + "..." if len(env_vars[var]) > 10 else env_vars[var]
            print_status(f"{var} is set ({masked})", 'ok')
    
    return all_ok


def check_credentials_file():
    """Check if Google Cloud credentials file exists and is valid."""
    print("\n2. Checking Google Cloud credentials...")
    
    # Get path from .env
    creds_path = None
    if Path('.env').exists():
        with open('.env') as f:
            for line in f:
                if line.strip().startswith('GOOGLE_APPLICATION_CREDENTIALS='):
                    creds_path = line.split('=', 1)[1].strip()
                    break
    
    if not creds_path:
        print_status("GOOGLE_APPLICATION_CREDENTIALS not set", 'error')
        return False
    
    creds_file = Path(creds_path)
    if not creds_file.exists():
        print_status(f"Credentials file not found: {creds_path}", 'error')
        print_status("Download service account key from Google Cloud Console", 'info')
        return False
    
    print_status(f"Credentials file exists: {creds_path}", 'ok')
    
    # Try to parse JSON
    try:
        with open(creds_file) as f:
            creds = json.load(f)
        
        required_keys = ['type', 'project_id', 'private_key', 'client_email']
        for key in required_keys:
            if key not in creds:
                print_status(f"Missing key in credentials: {key}", 'error')
                return False
        
        print_status(f"Project ID: {creds['project_id']}", 'ok')
        print_status(f"Service Account: {creds['client_email']}", 'ok')
        
        if creds.get('type') != 'service_account':
            print_status("Not a service account key", 'warning')
        
    except json.JSONDecodeError:
        print_status("Invalid JSON in credentials file", 'error')
        return False
    except Exception as e:
        print_status(f"Error reading credentials: {e}", 'error')
        return False
    
    return True


def check_podman():
    """Check if Podman is installed and running."""
    print("\n3. Checking Podman installation...")
    
    # Check if podman command exists
    import subprocess
    
    try:
        result = subprocess.run(
            ['podman', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            version = result.stdout.strip()
            print_status(f"Podman installed: {version}", 'ok')
        else:
            print_status("Podman command failed", 'error')
            return False
    except FileNotFoundError:
        print_status("Podman not installed", 'error')
        print_status("Install from: https://podman.io/getting-started/installation", 'info')
        return False
    except subprocess.TimeoutExpired:
        print_status("Podman command timed out", 'error')
        return False
    
    # Check if podman machine is running (macOS)
    if sys.platform == 'darwin':
        try:
            result = subprocess.run(
                ['podman', 'machine', 'list'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if 'Running' in result.stdout:
                print_status("Podman machine is running", 'ok')
            else:
                print_status("Podman machine not running", 'warning')
                print_status("Run: podman machine start", 'info')
        except Exception as e:
            print_status(f"Could not check machine status: {e}", 'warning')
    
    return True


def check_port():
    """Check if port 8080 is available."""
    print("\n4. Checking port availability...")
    
    import socket
    
    port = 8080
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    
    try:
        result = sock.connect_ex(('localhost', port))
        if result == 0:
            print_status(f"Port {port} is already in use", 'warning')
            print_status("You may need to stop the existing service or use a different port", 'info')
            return False
        else:
            print_status(f"Port {port} is available", 'ok')
            return True
    except Exception as e:
        print_status(f"Could not check port: {e}", 'warning')
        return True
    finally:
        sock.close()


def check_network():
    """Check network connectivity to Google APIs."""
    print("\n5. Checking network connectivity...")
    
    import urllib.request
    
    endpoints = [
        ('speech.googleapis.com', 443, 'Speech-to-Text API'),
        ('texttospeech.googleapis.com', 443, 'Text-to-Speech API'),
        ('generativelanguage.googleapis.com', 443, 'Gemini API'),
    ]
    
    all_ok = True
    for host, port, name in endpoints:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        
        try:
            result = sock.connect_ex((host, port))
            if result == 0:
                print_status(f"{name} is reachable", 'ok')
            else:
                print_status(f"{name} is not reachable", 'error')
                all_ok = False
        except Exception as e:
            print_status(f"Could not check {name}: {e}", 'warning')
            all_ok = False
        finally:
            sock.close()
    
    return all_ok


def check_dependencies():
    """Check if required Python packages are listed in requirements.txt."""
    print("\n6. Checking dependencies...")
    
    if not Path('requirements.txt').exists():
        print_status("requirements.txt not found", 'error')
        return False
    
    print_status("requirements.txt exists", 'ok')
    
    required_packages = [
        'aiortc',
        'aiohttp',
        'websockets',
        'google-cloud-speech',
        'google-cloud-texttospeech',
        'google-generativeai',
        'numpy',
    ]
    
    with open('requirements.txt') as f:
        content = f.read().lower()
    
    all_ok = True
    for package in required_packages:
        if package.lower() in content:
            print_status(f"{package} listed", 'ok')
        else:
            print_status(f"{package} not listed", 'error')
            all_ok = False
    
    return all_ok


def check_files():
    """Check if all required files exist."""
    print("\n7. Checking required files...")
    
    required_files = [
        ('main.py', 'Main application'),
        ('signaling_server.py', 'Signaling server'),
        ('peer_connection_handler.py', 'Peer connection handler'),
        ('audio_processor.py', 'Audio processor'),
        ('audio_track.py', 'Audio track'),
        ('ai_assistant.py', 'AI assistant'),
        ('Containerfile', 'Container definition'),
        ('requirements.txt', 'Dependencies'),
    ]
    
    all_ok = True
    for filename, description in required_files:
        if Path(filename).exists():
            print_status(f"{description}: {filename}", 'ok')
        else:
            print_status(f"{description} not found: {filename}", 'error')
            all_ok = False
    
    return all_ok


def main():
    """Run all validation checks."""
    print("=" * 60)
    print("AI Assistant Configuration Validator")
    print("=" * 60)
    
    checks = [
        check_env_file,
        check_credentials_file,
        check_podman,
        check_port,
        check_network,
        check_dependencies,
        check_files,
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print_status(f"Check failed with error: {e}", 'error')
            results.append(False)
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    if all(results):
        print_status(f"All checks passed ({passed}/{total})", 'ok')
        print("\n✨ Your configuration looks good! Ready to start.")
        print("\nNext steps:")
        print("  ./quickstart.sh        # Quick start")
        print("  ./run.sh start         # Build and run")
        print()
        return 0
    else:
        print_status(f"Some checks failed ({passed}/{total} passed)", 'error')
        print("\n❌ Please fix the issues above before starting.")
        print("\nFor help, see:")
        print("  SETUP.md        # Setup guide")
        print("  README.md       # Documentation")
        print()
        return 1


if __name__ == '__main__':
    sys.exit(main())
