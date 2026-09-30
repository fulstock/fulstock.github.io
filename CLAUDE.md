# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

`AGENTS.md` and `.github/` instruction files are generic upstream al-folio docs. This file covers what is specific to **this** site: Igor Rozhkov's personal academic site (https://fulstock.github.io, a user site, so `baseurl` stays empty), forked from al-folio. Deployed to GitHub Pages by `.github/workflows/deploy.yml` when `main` gets a push.

## Commands

- Dev server: `docker compose up` → http://localhost:8080 (Windows host: Docker is the only practical route, since the non-Docker setup needs Ruby and ImageMagick)
- Format (CI runs Prettier on PRs): `npx prettier . --write`. On this Windows checkout (`core.autocrlf=true`), use `npx prettier --check --end-of-line auto <files>`. Otherwise every file fails on CRLF.
- The user pushes. Never `git push`. `deploy.yml` re-renders the PDF CV on every deploy, so the live PDF always matches the current bib and `cv.yml`.
- Render the PDF CV locally (same steps as CI):
  ```bash
  pip install -r requirements.txt
  python scripts/bib_to_cv_publications.py
  rendercv render _data/cv.yml --settings assets/rendercv/settings.yaml
  git checkout -- _data/cv.yml   # REQUIRED — the script rewrites cv.yml destructively
  ```

There are no tests.

## Where content lives

| What                               | File                                                                  |
| ---------------------------------- | --------------------------------------------------------------------- |
| Publications (web + both CVs)      | `_bibliography/papers.bib`                                            |
| CV sections (web CV + PDF CV)      | `_data/cv.yml` (RenderCV format)                                      |
| Home page bio / subtitle / sidebar | `_pages/about.md`                                                     |
| Social links                       | `_data/socials.yml`                                                   |
| Enabled nav pages                  | `about`, `publications`, `cv`. The other `_pages/*` have `nav: false` |

## Publication / CV pipeline (spans several files)

`papers.bib` is the single source of truth for publications. It feeds three outputs:

1. **Publications page and home "selected papers"**: jekyll-scholar with `_layouts/bib.liquid`. `selected = {true}` puts an entry on the home page. Button fields (`abbr`, `pdf`, `arxiv`, `code`, `html`, `google_scholar_id`, …) are listed in `filtered_bibtex_keywords` in `_config.yml`.
2. **Web CV** (`_pages/cv.md`, `cv_format: rendercv`): `_layouts/cv.liquid` renders `cv.yml` sections but **skips** any `Publications` section. It renders publications from BibTeX through the custom `_layouts/bib_cv.liquid`, which prefers `title_en` / `journal_en` / `booktitle_en`.
3. **PDF CV**: `.github/workflows/render-cv.yml` runs when `cv.yml`, `papers.bib`, the script, or `assets/rendercv/*.yaml` change. `scripts/bib_to_cv_publications.py` parses the bib (stdlib regex parser, not a real BibTeX library), injects a `Publications` section into `cv.yml` before `Education`, and strips top-level `cv` keys that RenderCV rejects (`label`, `image`, `Research Interests`, …). CI then renders the PDF, restores `cv.yml`, and commits only `assets/rendercv/rendercv_output/Igor_Rozhkov_CV.pdf` as `chore: render the latest CV`. Pull before pushing after a bib/CV change, because CI commits land on `main`.

Conventions that follow from this:

- Russian-language papers keep the original fields plus `author_en`, `title_en`, `booktitle_en`/`journal_en`. The PDF CV and web CV use the `_en` variants. The publications page shows the originals.
- The script bolds any author containing `Rozhkov`/`Рожков`. It drops "authors" with ≥2 commas as institutional noise. jekyll-scholar does **not** drop them, so keep real names only in `author`.
- Write accented names as Unicode (`Rodríguez`), not LaTeX (`{\'\i}`). The script's LaTeX cleanup doesn't handle accent commands. Also strip non-breaking spaces from publisher exports (Springer BibTeX contains them). `and others` becomes "et al." in the PDF.
- Include `month` where possible. The script sorts by the `YYYY` / `YYYY-MM` string, so an entry without a month sorts below same-year entries that have one.
- Top-level `cv.Research Interests` (keyword list) is for the web CV. The `sections.Research Interests` string is for the PDF. The web layout skips the latter.
- `Conference Presentations` and `Awards` sections render through `_includes/cv/awards.liquid` (`name`, `date`, `highlights`).

## Other customizations vs upstream

Changed from upstream al-folio: `_layouts/cv.liquid`, `_layouts/bib_cv.liquid` (new), `_layouts/about.liquid`, `_includes/cv/{awards,skills,languages}.liquid`, `_includes/selected_papers.liquid`, `_includes/footer.liquid`, `_sass/_components.scss`, `deploy.yml`, `render-cv.yml`. Keep these changes when merging upstream al-folio updates.
