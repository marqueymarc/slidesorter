# Contributing

Thank you for improving SlideSorter.

## Before opening an issue

Search existing issues. Remove private filenames and paths from logs. Reproduce problems with synthetic media whenever possible.

## Propose a change

Open an issue for substantial behavioral, storage, or security changes. Explain the workflow and failure recovery.

Small fixes may go directly to a pull request.

## Prepare a checkout

```sh
git clone https://github.com/marqueymarc/slidesorter.git
cd slidesorter
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

## Make changes

- Preserve localhost binding as the default.
- Preserve path validation before filesystem actions.
- Preserve journal-before-move ordering.
- Avoid dependencies unless they materially simplify safety or portability.
- Keep generated state outside the repository.
- Use synthetic fixtures only.
- Update documentation with user-visible changes.
- Add tests for path, move, Undo, and range behavior.

## Validate

```sh
python -m unittest discover -s tests -v
python -m compileall -q src tests
node --check src/slidesorter/assets/app.js
node --check src/slidesorter/assets/history.js
```

## Submit

Describe:

- the problem;
- the chosen behavior;
- safety implications;
- state migrations;
- tests performed.

Never include real catalogs, thumbnails, action history, or media.
