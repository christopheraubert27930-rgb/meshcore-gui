#!/usr/bin/env python3
"""
MeshCore GUI - Threaded BLE Edition
====================================

Thin wrapper that delegates to the package entry point.
All application logic lives in :mod:`meshcore_gui.__main__`.

Usage:
    python meshcore_gui.py <BLE_ADDRESS>
    python meshcore_gui.py <BLE_ADDRESS> --debug-on
    python -m meshcore_gui <BLE_ADDRESS>

                   Author: PE1HVH
                  Version: 5.0
  SPDX-License-Identifier: MIT
                Copyright: (c) 2026 PE1HVH
"""

from meshcore_gui.__main__ import main

if __name__ == "__main__":
    main()
