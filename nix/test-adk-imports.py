#!/usr/bin/env python3
"""
ADK import validation test script — NIX-01.

Run this script INSIDE a NixOS LXC container built from nix/configuration.nix
to validate that the google-adk, langgraph, and weaviate-client Nix expressions
install correctly and all imports succeed.

Usage (inside NixOS LXC container):
    cd /path/to/nix
    python test-adk-imports.py

Expected output:
    ADK imports OK

Exit code 0 = all imports succeeded (NIX-01 accepted).
Exit code 1 = one or more imports failed (check NixOS Nix expression for missing deps).
"""

import sys

_failed = False

def check_import(module_path: str, display_name: str) -> None:
    global _failed
    try:
        __import__(module_path)
        print(f"  OK: {display_name}")
    except ImportError as e:
        print(f"  FAIL: {display_name} — {e}", file=sys.stderr)
        _failed = True


check_import("google.adk", "google.adk (google-adk 2.2.0)")
check_import("langgraph", "langgraph (langgraph 1.2.5)")
check_import("weaviate", "weaviate (weaviate-client 4.21.3)")

if _failed:
    print("ADK imports FAILED — see errors above", file=sys.stderr)
    sys.exit(1)

print("ADK imports OK")
sys.exit(0)
