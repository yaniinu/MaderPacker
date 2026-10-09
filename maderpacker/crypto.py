"""Vendor container key material.

These bytes were recovered from the vendor's own binary and are required to
decrypt song blocks the user's app already decrypts at playback time.
Keep them ONLY in this file; never log, print, or copy them into docs,
issues, or release notes.
"""

MIDI_KEY = bytes.fromhex(
    "9eac94f7d1abf0c1e08e9f67d3a2f6fc"
    "45fda31d2477702dae565b259c49fe6b"
)
MIDI_IV = bytes.fromhex("4a744e704f62417636373134402a2326")
