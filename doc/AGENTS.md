# AGENTS.md

## FileGraph Working Rules

- Branch roles:
  - `main`: stable baseline branch. Keep it free of AI feature UI, API-key handling, AI dependencies, and AI policy docs.
  - `dev`: general development branch based on the current `main` behavior. Use it for non-AI fixes, UI polish, docs, tests, and product features.
  - `dev-ai`: AI feature development branch. Keep AI settings, API-provider work, AI relationship suggestions, and AI folder-organization experiments here until they are explicitly approved for merge.
- After doing project work, always review and update `README.md`, `doc/SPEC.md`, and `doc/USAGE.md` when the behavior, UI, workflow, or known future work changed.
- Do not run a build unless the user explicitly asks for a build. When there is no direct build request, record requested or discovered follow-up changes as notes first.
- Always clean up unnecessary byproduct files created during work, such as temporary build artifacts, stray generated files, or obsolete scratch files.
