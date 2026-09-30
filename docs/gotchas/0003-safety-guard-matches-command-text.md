---
status: active
date: 2026-09-30
tags: [hooks, agents]
---
# The safety guard blocks commands whose text mentions writing to build/

## Symptom
A shell command is denied with "Files under build/ are generated" even though it does not
write to `build/`. Example: a heredoc or `python -c` that edits a workflow file whose content
contains `cp build/state/dashboard.html ...`.

## What to do
The guard matches command text, not what the command does: any `cp`, `mv`, `rm`, `tee` or
`sed -i` followed by `build/` on the same line is denied. Do not rephrase the command to slip
past the pattern. Edit the file with the Edit tool instead (a workflow file then asks the
human, as it should), and build views only with `python -m scripts.build_state`.
