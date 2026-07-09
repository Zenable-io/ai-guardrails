---
description: Add tests for specified code, ensuring they test core concepts without overfitting
---

Add tests for $ARGUMENTS. We want to make sure our tests are reasonable and don't overfit the solution, we do not want to crystalize the code base. They should test core concepts and fundamental capabilities or prevent bugs from recurring, but do not need to test every single line or edge case. If you are fixing a bug, after writing the tests, run the tests (using the appropriate test command for this repository, such as `task test`, `npm test`, `pytest`, etc.) and it should pass. Then revert the source code changes from this branch to ensure that the tests FAIL when the fix is not in place, then put the exact same source code changes back in place, re-run the tests and ensure that they all pass again. Iterate until all of the tests pass. Use parameterized tests instead of for loops when testing different scenarios.
