# Contributing

Issues and focused pull requests are welcome.

Before sending a patch:

1. Run the fast gate: `python harness/scripts/verify_fast.py` with the harness
   running on `127.0.0.1:8766`.
2. Add or update a test for behavior changes.
3. Update the relevant doc in the same change.
4. Keep credentials out of the repo. Use the gitignored `.env` or environment
   variables; `.env.example` documents the available settings.

By submitting a patch, you certify that you have the right to contribute it
under the project's Apache-2.0 license. Signing off (`git commit -s`) is
appreciated but not required.
