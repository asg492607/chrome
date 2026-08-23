# Developer Guide

Welcome to PacketForge development.

## Setup
1. Use `pip install -r requirements.txt` (if generated).
2. Run tests via `pytest`.
3. Launch via `python application/packetforge.py`.

## Adding a feature
Ensure features are decoupled by publishing events to the `EventBus` rather than hardcoding cross-module function calls.
