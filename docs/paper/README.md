# Paper

`afaw.tex` is the white paper. Its appendix is generated from `AGENTS.md`, so the rules exist in
one place only; the figures are the ones in `docs/img/`, rendered from `docs/diagrams/*.dot`.

Build (XeLaTeX, Liberation Sans or Arial installed):

```bash
python -m scripts.rules_to_tex AGENTS.md docs/paper/appendix_rules.tex
cd docs/paper
xelatex afaw.tex && xelatex afaw.tex
```

`appendix_rules.tex` and the LaTeX build files are generated and ignored by git. The published
PDF is archived on Zenodo: https://doi.org/10.5281/zenodo.23050310
