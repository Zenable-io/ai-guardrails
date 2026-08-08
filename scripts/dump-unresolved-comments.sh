#!/usr/bin/env bash
set -euo pipefail

# Script to dump unresolved PR comments in XML format for LLM consumption
# Usage: ./dump-unresolved-comments.sh <PR_NUMBER>

PR_NUMBER="${1:-}"

if [ -z "$PR_NUMBER" ]; then
    echo "Usage: $0 <PR_NUMBER>" >&2
    exit 1
fi

if ! [[ "$PR_NUMBER" =~ ^[0-9]+$ ]]; then
    echo "ERROR: PR_NUMBER must be a positive integer, got '$PR_NUMBER'" >&2
    exit 1
fi

# Get repo owner and name
REPO_INFO=$(gh repo view --json owner,name)
OWNER=$(jq -r '.owner.login' <<<"$REPO_INFO")
REPO=$(jq -r '.name' <<<"$REPO_INFO")

# The owner, repo, and PR number reach GitHub as typed GraphQL variables rather than
# as text spliced into the query, so a value carrying quotes or braces is data and
# cannot become query structure.
# shellcheck disable=SC2016  # $owner and friends are GraphQL variables; the shell must leave them alone
QUERY='query($owner: String!, $repo: String!, $pr: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isResolved
          path
          line
          startLine
          comments(first: 100) { nodes { author { login } body } }
        }
      }
    }
  }
}'

# Function to fetch all review threads with pagination
fetch_all_threads() {
    local cursor=""
    local has_next=true
    local all_threads="[]"
    local response threads

    while [ "$has_next" = "true" ]; do
        if [ -n "$cursor" ]; then
            response=$(gh api graphql -f query="$QUERY" \
                -f owner="$OWNER" -f repo="$REPO" -F pr="$PR_NUMBER" -f cursor="$cursor")
        else
            response=$(gh api graphql -f query="$QUERY" \
                -f owner="$OWNER" -f repo="$REPO" -F pr="$PR_NUMBER")
        fi

        threads=$(jq '.data.repository.pullRequest.reviewThreads.nodes' <<<"$response")
        all_threads=$(jq --argjson new "$threads" '. + $new' <<<"$all_threads")

        has_next=$(jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage' <<<"$response")
        cursor=$(jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor // ""' <<<"$response")

        if [ -z "$cursor" ]; then
            has_next=false
        fi
    done

    printf '%s' "$all_threads"
}

# Fetch all threads
ALL_THREADS=$(fetch_all_threads)

echo '<?xml version="1.0" encoding="UTF-8"?>'
echo '<pr_unresolved_comments>'
echo "  <pr_number>$PR_NUMBER</pr_number>"
echo "  <repository>${OWNER}/${REPO}</repository>"
echo '  <threads>'

# Each thread builds an array of lines that is only then flattened, so an absent line
# or startLine contributes no element at all. The previous version emitted an empty
# string and stripped it with `grep -v`, which exited 1 on a PR with nothing
# unresolved and, under `pipefail`, killed the script before the closing tags.
#
# A comment body is written by whoever reviewed the PR, so it is untrusted: `]]>`
# is split across two CDATA sections to keep a body from closing the section early,
# and a deleted author comes back as null rather than a login.
echo "$ALL_THREADS" | jq -r '
    .[] | select(.isResolved == false) |
    ["    <thread>", "      <file>" + (.path // "unknown") + "</file>"]
    + (if .line != null then ["      <line>" + (.line | tostring) + "</line>"] else [] end)
    + (if .startLine != null then ["      <start_line>" + (.startLine | tostring) + "</start_line>"] else [] end)
    + ["      <comments>"]
    + ([.comments.nodes[] |
        ["        <comment>",
         "          <author>" + (.author.login // "unknown") + "</author>",
         "          <body><![CDATA[" + ((.body // "") | gsub("\\]\\]>"; "]]]]><![CDATA[>")) + "]]></body>",
         "        </comment>"]
       ] | add // [])
    + ["      </comments>", "    </thread>"]
    | .[]
'

echo '  </threads>'
echo '</pr_unresolved_comments>'
