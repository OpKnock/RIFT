# Code Review

## Automated test gate (active)

GitHub Actions (`.github/workflows/test.yml`) installs `.[dev]` on Python 3.11
and runs `pytest`, validation gates (migrations, secret scan, version
consistency), and a Bandit SAST gate on every push to `main` and every pull
request. This is the repository's enforced verification gate.

## CodeRabbit (optional, not yet executed)

`.coderabbit.yaml` is checked in so that reviews can run **if and when** the
CodeRabbit GitHub App is installed on `OpKnock/RIFT` with pull-request scope:

1. Install CodeRabbit from the GitHub Marketplace onto the repository.
2. Open a pull request — CodeRabbit posts inline findings automatically.
3. Check the PR "Checks" tab for the CodeRabbit run before treating any
   comment as an executed review.

Status honesty rule: do **not** claim "CodeRabbit reviewed release X" unless
a CodeRabbit check run is visible on the corresponding PR/commit. As of this
commit, no CodeRabbit execution connector or completed review run has been
observed from this environment, so no such claim is made. The config exists to
enable future reviews, not to imply a past one.
