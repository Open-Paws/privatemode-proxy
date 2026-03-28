#!/usr/bin/env python3
"""
API Key Management Script for Privatemode Proxy.

Usage:
    ./manage_keys.py generate [--description DESC] [--expires-days N] [--rate-limit N]
    ./manage_keys.py list
    ./manage_keys.py revoke <key_id>
    ./manage_keys.py rotate <key_id> [--expires-days N]

Examples:
    # Generate a new key
    ./manage_keys.py generate --description "Production API" --expires-days 90

    # List all keys
    ./manage_keys.py list

    # Revoke a key
    ./manage_keys.py revoke key_abc123

    # Rotate a key (disable old, create new)
    ./manage_keys.py rotate key_abc123 --expires-days 90
"""

import argparse
import hashlib
import json
import os
import secrets
import sys
import time
from datetime import datetime
from pathlib import Path

KEYS_FILE = Path(__file__).parent.parent / "secrets" / "api_keys.json"


def load_keys() -> dict:
    """Load keys from file."""
    if not KEYS_FILE.exists():
        return {"keys": []}
    with open(KEYS_FILE) as f:
        return json.load(f)


def save_keys(data: dict) -> None:
    """Save keys to file."""
    KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(KEYS_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Keys saved to {KEYS_FILE}")


def generate_key(prefix: str = "pm") -> str:
    """Generate a new secure API key."""
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}_{random_part}"


def hash_key(key: str) -> str:
    """Hash an API key."""
    return hashlib.sha256(key.encode()).hexdigest()


def format_timestamp(ts: float | None) -> str:
    """Format a timestamp for display."""
    if ts is None:
        return "Never"
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def cmd_generate(args):
    """Generate a new API key."""
    data = load_keys()

    # Generate key
    key = generate_key()
    key_hash = hash_key(key)
    key_id = f"key_{secrets.token_hex(4)}"

    entry = {
        "key_id": key_id,
        "key_hash": key_hash,
        "created_at": time.time(),
        "description": args.description or "",
        "enabled": True
    }

    if args.expires_days:
        entry["expires_at"] = time.time() + (args.expires_days * 86400)

    if args.rate_limit:
        entry["rate_limit"] = args.rate_limit

    data["keys"].append(entry)
    save_keys(data)

    print("\n" + "=" * 60)
    print("NEW API KEY GENERATED")
    print("=" * 60)
    print(f"Key ID:      {key_id}")
    print(f"API Key:     {key}")
    print(f"Description: {args.description or '(none)'}")
    if args.expires_days:
        print(f"Expires:     {format_timestamp(entry['expires_at'])}")
    if args.rate_limit:
        print(f"Rate Limit:  {args.rate_limit} req/min")
    print("=" * 60)
    print("\nIMPORTANT: Save this key now. It cannot be retrieved later!")
    print("The proxy will automatically detect the new key.\n")

    return key


def cmd_list(args):
    """List all API keys."""
    data = load_keys()

    if not data["keys"]:
        print("No API keys configured.")
        return

    print("\n" + "=" * 80)
    print("API KEYS")
    print("=" * 80)

    for key in data["keys"]:
        status = "ENABLED" if key.get("enabled", True) else "DISABLED"

        # Check expiration
        expires_at = key.get("expires_at")
        if expires_at and time.time() > expires_at:
            status = "EXPIRED"

        print(f"\nKey ID:      {key['key_id']}")
        print(f"Status:      {status}")
        print(f"Description: {key.get('description', '(none)')}")
        print(f"Created:     {format_timestamp(key.get('created_at'))}")
        print(f"Expires:     {format_timestamp(expires_at)}")
        if key.get("rate_limit"):
            print(f"Rate Limit:  {key['rate_limit']} req/min")
        print("-" * 40)

    print(f"\nTotal: {len(data['keys'])} keys")


def cmd_revoke(args):
    """Revoke an API key."""
    data = load_keys()

    found = False
    for key in data["keys"]:
        if key["key_id"] == args.key_id:
            key["enabled"] = False
            key["revoked_at"] = time.time()
            found = True
            break

    if not found:
        print(f"Error: Key ID '{args.key_id}' not found.")
        sys.exit(1)

    save_keys(data)
    print(f"Key '{args.key_id}' has been revoked.")
    print("The proxy will automatically detect this change.")


def cmd_rotate(args):
    """Rotate an API key (revoke old, generate new)."""
    data = load_keys()

    # Find and revoke old key
    old_key = None
    for key in data["keys"]:
        if key["key_id"] == args.key_id:
            old_key = key
            key["enabled"] = False
            key["revoked_at"] = time.time()
            key["rotated_to"] = None  # Will be set below
            break

    if not old_key:
        print(f"Error: Key ID '{args.key_id}' not found.")
        sys.exit(1)

    # Generate new key with same settings
    new_key = generate_key()
    new_key_hash = hash_key(new_key)
    new_key_id = f"key_{secrets.token_hex(4)}"

    entry = {
        "key_id": new_key_id,
        "key_hash": new_key_hash,
        "created_at": time.time(),
        "description": old_key.get("description", "") + " (rotated)",
        "enabled": True,
        "rotated_from": args.key_id
    }

    if args.expires_days:
        entry["expires_at"] = time.time() + (args.expires_days * 86400)
    elif old_key.get("expires_at"):
        # Keep same expiration policy
        original_duration = old_key["expires_at"] - old_key.get("created_at", time.time())
        entry["expires_at"] = time.time() + original_duration

    if old_key.get("rate_limit"):
        entry["rate_limit"] = old_key["rate_limit"]

    # Update reference in old key
    old_key["rotated_to"] = new_key_id

    data["keys"].append(entry)
    save_keys(data)

    print("\n" + "=" * 60)
    print("KEY ROTATED")
    print("=" * 60)
    print(f"Old Key ID:  {args.key_id} (revoked)")
    print(f"New Key ID:  {new_key_id}")
    print(f"New API Key: {new_key}")
    print("=" * 60)
    print("\nIMPORTANT: Update your applications with the new key!")
    print("The proxy will automatically detect these changes.\n")


def cmd_delete(args):
    """Permanently delete a key from the file."""
    data = load_keys()

    original_count = len(data["keys"])
    data["keys"] = [k for k in data["keys"] if k["key_id"] != args.key_id]

    if len(data["keys"]) == original_count:
        print(f"Error: Key ID '{args.key_id}' not found.")
        sys.exit(1)

    save_keys(data)
    print(f"Key '{args.key_id}' has been permanently deleted.")


def main():
    parser = argparse.ArgumentParser(
        description="Manage API keys for Privatemode proxy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate a new API key")
    gen_parser.add_argument("--description", "-d", help="Description for the key")
    gen_parser.add_argument("--expires-days", "-e", type=int, help="Days until expiration")
    gen_parser.add_argument("--rate-limit", "-r", type=int, help="Rate limit (requests per minute)")

    # List command
    subparsers.add_parser("list", help="List all API keys")

    # Revoke command
    revoke_parser = subparsers.add_parser("revoke", help="Revoke an API key")
    revoke_parser.add_argument("key_id", help="The key ID to revoke")

    # Rotate command
    rotate_parser = subparsers.add_parser("rotate", help="Rotate an API key")
    rotate_parser.add_argument("key_id", help="The key ID to rotate")
    rotate_parser.add_argument("--expires-days", "-e", type=int, help="Days until expiration for new key")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Permanently delete a key")
    delete_parser.add_argument("key_id", help="The key ID to delete")

    args = parser.parse_args()

    commands = {
        "generate": cmd_generate,
        "list": cmd_list,
        "revoke": cmd_revoke,
        "rotate": cmd_rotate,
        "delete": cmd_delete,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
