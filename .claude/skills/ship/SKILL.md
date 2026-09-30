---
name: ship
description: Runs the local verification tier and, if it passes, commits and pushes the task branch so CI verifies the rest.
---

# `ship` Skill

Use this skill when the user asks to "ship", "test and ship", or uses `/ship`.

1. **Guard**: check the current branch (`git branch --show-current`). If it is `main`, stop:
   AGENTS.md section 18 forbids committing to `main`. Create the task branch first.
2. **Local tier**: follow the `tests` skill (the tests being written, ruff on the diff).
   The full suite and the heavy checks run in CI, not here.
3. If the local tier fails, stop. Do not commit or push; fix the errors or tell the user.
4. **Commit**: follow the `commit` skill (stage named files, Conventional Commits message).
5. **Push**: `git push -u origin <branch>` (or `git push` if it already has an upstream).
6. Report the CI run link once it starts; do not describe the change as passing before CI does.
