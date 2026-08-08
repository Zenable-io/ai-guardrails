#!/usr/bin/env python3
"""A stand-in for the `gh` CLI so the prfeedback scripts can be tested offline.

The scripts talk to GitHub through exactly two shapes of `gh` call -- `gh repo view
--json owner,name` and `gh api graphql` with `-f`/`-F` variables -- so this replays
canned responses for both. Every invocation is appended to `$GH_STUB_LOG` as JSON,
which is what lets a test assert that a mutation was *not* sent.

Responses come from the JSON fixture at `$GH_STUB_FIXTURE`:

    {
      "repo": {"owner": {"login": "..."}, "name": "..."},
      "pages": [ <graphql response>, ... ],   # served in order, one per cursor hop
      "mutation": <graphql response>          # optional; defaults to a success
    }
"""

import json
import os
import sys


def load_fixture() -> dict:
    with open(os.environ["GH_STUB_FIXTURE"], encoding="utf-8") as handle:
        return json.load(handle)


def parse_variables(argv: list[str]) -> dict[str, str]:
    """Collect the `-f key=value` / `-F key=value` pairs `gh api graphql` accepts."""
    variables: dict[str, str] = {}
    index = 0
    while index < len(argv):
        if argv[index] in ("-f", "-F", "--field", "--raw-field"):
            key, _, value = argv[index + 1].partition("=")
            variables[key] = value
            index += 2
        else:
            index += 1
    return variables


def log_call(argv: list[str], variables: dict[str, str]) -> None:
    path = os.environ.get("GH_STUB_LOG")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"argv": argv, "variables": variables}) + "\n")


def main() -> int:
    argv = sys.argv[1:]
    fixture = load_fixture()

    if argv[:2] == ["repo", "view"]:
        log_call(argv, {})
        print(json.dumps(fixture["repo"]))
        return 0

    if argv[:2] == ["api", "graphql"]:
        variables = parse_variables(argv)
        log_call(argv, variables)
        query = variables.get("query", "")

        if query.lstrip().startswith("mutation"):
            print(json.dumps(fixture.get("mutation", {
                "data": {"addPullRequestReviewThreadReply": {"comment": {"id": "stub-comment-id"}}}
            })))
            return 0

        # `cursor` is absent on the first request, then carries the previous page's
        # endCursor, so its presence selects which canned page to serve.
        pages = fixture["pages"]
        cursor = variables.get("cursor")
        index = 0 if cursor is None else next(
            (i for i, page in enumerate(pages) if page.get("_cursor") == cursor), 0
        )
        page = {k: v for k, v in pages[index].items() if k != "_cursor"}
        print(json.dumps(page))
        return 0

    print(f"gh_stub: unsupported invocation: {argv}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
