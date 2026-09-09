# Kling Prompt Deterministic Validator

This repository runs a reproducible GitHub Actions audit for the frozen Kling prompt candidate.

- Locked candidate SHA-256: `b94f9ad3f37ba8740477cf8337343f5b9f55d66e832b0c893a6ada6b0de1d639`
- Tests: T01–T11
- Mutation suite: one designated corruption per test; each designated mutation must fail its corresponding test, while unrelated tests remain evaluable.
- Fail closed: any SHA mismatch, baseline failure, or invalid mutation suite causes workflow failure.

This is deterministic CI validation. It verifies structural/source/sequence/negative/boundary/end-lock rules encoded in `validator.py`; it does not guarantee Kling's rendered visual quality and is not an independent LLM judge.
