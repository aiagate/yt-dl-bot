# Black-box acceptance-test rules

You are responsible for adding and maintaining black-box acceptance tests.

## Allowed inputs

Read only the following paths before writing a test:

- `acceptance/contracts/`
- `acceptance/support/`
- `acceptance/tests/`
- `acceptance/run-tests`

Do not read `src/`, `tests/`, or the architecture sections of `README.md`.
They describe or test the implementation and are intentionally outside this
exercise.

## Test design

- Treat the functions in `acceptance/support/` as the complete test interface.
- Verify visible inputs, outputs, and effects described by a contract.
- Do not import application modules directly from tests.
- Do not mock private modules, assert call counts, or assert implementation
  order.
- Keep each test traceable to a contract statement by using a descriptive test
  name or a short comment.

## Verification and handoff

Run `./acceptance/run-tests` after changing tests. In your handoff, list the
contract file(s) you used and the behaviours covered. State if a needed
behaviour is missing from the contracts instead of inferring it from source.
