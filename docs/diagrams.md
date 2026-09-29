# Diagrams: snippets to copy and paste

All diagrams are rendered from `docs/diagrams/*.dot`. Use the SVG in a README (GitHub shows it inline) and the PNG anywhere SVG does not render (Medium, LinkedIn, PDF papers, slides). Colors: blue = agent action, amber = human, green = CI or deterministic check, purple = state files, red = blocked.

| # | Diagram | SVG | PNG | Best place |
|---|---|---|---|---|
| 1 | Overview | `docs/img/01-overview.svg` | `docs/img/01-overview.png` | Top of the README, paper introduction |
| 2 | Life of a task | `docs/img/02-task-lifecycle.svg` | `docs/img/02-task-lifecycle.png` | "How to use it" |
| 3 | State and context | `docs/img/03-state-and-context.svg` | `docs/img/03-state-and-context.png` | "Isolated state per task" |
| 4 | CI pipeline | `docs/img/04-ci-pipeline.svg` | `docs/img/04-ci-pipeline.png` | "Validation runs in CI" |
| 5 | Mutation testing | `docs/img/05-mutation-testing.svg` | `docs/img/05-mutation-testing.png` | "Mutation testing on the diff" |
| 6 | Control layers | `docs/img/06-control-layers.svg` | `docs/img/06-control-layers.png` | "Human in the loop" |

## Markdown snippets

```markdown
![AFAW overview: the human opens one isolated terminal per agent, each agent works on its own branch, CI validates in the cloud, and the human approves every PR before it reaches main.](docs/img/01-overview.svg)

![Life of a task in 12 steps, from asking for a ROL to deleting the branch after the merge.](docs/img/02-task-lifecycle.svg)

![State and context: the agent writes only its delta and task file; CI regenerates the shared state and opens a state PR that the human approves.](docs/img/03-state-and-context.svg)

![CI pipeline: path filters route a push to parallel jobs; document-only changes run nothing.](docs/img/04-ci-pipeline.svg)

![Mutation testing flow: baseline, mutants, re-run, fix survivors, block the PR when a mandatory file is below the minimum score.](docs/img/05-mutation-testing.svg)

![Control layers: advice in AGENTS.md, hooks, CI checks, branch protection, human approval.](docs/img/06-control-layers.svg)
```

## Editing a diagram

1. Edit the matching file in `docs/diagrams/`.
2. Run `node scripts/build_diagrams.mjs`.
3. Look at the new PNG before committing: long labels can widen a box, and a changed edge can reroute the layout.
