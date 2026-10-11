# Contributing to AtlasBridge

Thanks for helping make N-ATLaS easier for every Nigerian developer to build with. Bug reports, fixes, docs, translations and new features are all welcome.

## Ways to contribute

- **Report a bug or suggest a feature.** Open a GitHub issue. Include what you did, what you expected and what happened. For language problems, paste the exact text you sent.
- **Improve language handling.** Add phrases to `gateway/tests/lang_eval.py` (everyday Hausa, Igbo, Yoruba or English, with or without diacritics) or improve `gateway/app/language.py`. Native speakers are especially welcome.
- **Improve docs and examples.** Fix unclear steps in `README.md` or add example apps that use the SDK.
- **Write code.** See the roadmap ideas below, or pick any open issue.

## Development setup

You don't need a GPU. Mock mode returns canned replies.

```bash
git clone https://github.com/Kingsmichaei/atlasbridge.git
cd atlasbridge/gateway
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt pytest openai
cp .env.example .env            # set MOCK_UPSTREAM=1 to develop without a model server
uvicorn app.main:app --reload   # playground at http://localhost:8000
pytest -q                       # all tests must pass
```

To work on the SDK, run `pip install -e sdk` from the repo root.

To test against the real model, run the Kaggle notebook in `serving/` and set `UPSTREAM_URL` and `UPSTREAM_KEY` in `.env`.

## Making a change

1. Fork the repo and create a branch: `git checkout -b fix/short-description`.
2. Keep changes focused: one fix or feature per pull request.
3. Add or update tests in `gateway/tests/` for any behaviour you change.
4. Run `pytest -q` and make sure everything passes.
5. Update `README.md` and `CHANGELOG.md` (under an "Unreleased" heading) if users will notice the change.
6. Open a pull request that explains what changed and why. Link the issue it fixes.

## Code style

- Python 3.10+, type hints on public functions, short docstrings that say *why* as well as *what*.
- Keep the API OpenAI-compatible. AtlasBridge-specific additions go in optional fields (like `language`) or under `x_atlasbridge` in responses, so existing OpenAI clients keep working.
- All model calls must go to N-ATLaS. Don't add other foundation models.

## Roadmap ideas

- `/v1/audio/transcriptions` using the N-ATLaS ASR models
- JavaScript/TypeScript SDK
- Publish the Python SDK to PyPI
- Per-key quotas and a usage dashboard
- vLLM serving for concurrent requests on a persistent GPU

## Responsible use

AtlasBridge is built on N-ATLaS and must follow the [N-ATLaS Terms of Use](https://huggingface.co/NCAIR1/N-ATLaS): attribution, the 1,000-active-user cap without a commercial licence, and the prohibited uses listed there. Don't submit personal data in test prompts or issues.

Be respectful and constructive in issues and reviews. We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

## Licence

By contributing, you agree that your contributions are licensed under the MIT License (see `LICENSE`). N-ATLaS itself is licensed separately by Awarri Technologies and FMCIDE.

> N-ATLaS is an initiative of the Federal Ministry of Communications, Innovation and Digital Economy, and powered by Awarri Technologies.
