#!/usr/bin/env python3
"""
Basic import test - verifies package can be imported without pytest dependency.
"""

import importlib
import sys

MODULE_NAME = "psd_toolkit"


def main():
    try:
        # Test basic import
        importlib.import_module(MODULE_NAME)
        print(f"✓ Successfully imported {MODULE_NAME}")

    except Exception as e:
        print(
            f"✗ Failed to import {MODULE_NAME}: {e}", file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
