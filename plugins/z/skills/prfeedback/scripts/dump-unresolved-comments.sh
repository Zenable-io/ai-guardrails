#!/usr/bin/env bash
set -euo pipefail

# Script to dump unresolved PR comments in XML format for LLM consumption
# Usage: ./dump-unresolved-comments.sh <PR_NUMBER>

PR_NUMBER="${1:-}"

if [ -z "$PR_NUMBER" ]; then
    echo "Usage: $0 <PR_NUMBER>" >&2
    exit 1
fi

# Get repo owner and name
REPO_INFO=$(gh repo view --json owner,name)
OWNER=$(echo "$REPO_INFO" | jq -r '.owner.login')
REPO=$(echo "$REPO_INFO" | jq -r '.name')

echo '<?xml version="1.0" encoding="UTF-8"?>'
echo '<pr_unresolved_comments>'
echo "  <pr_number>$PR_NUMBER</pr_number>"
echo "  <repository>${OWNER}/${REPO}</repository>"
echo '  <threads>'

# Function to fetch all review threads with pagination
fetch_all_threads() {
    local cursor=""
    local has_next=true
    local all_threads="[]"

    while [ "$has_next" = "true" ]; do
        local cursor_arg=""
        if [ -n "$cursor" ]; then
            cursor_arg=", after: \"$cursor\""
        fi

        local query="{ repository(owner: \"$OWNER\", name: \"$REPO\") { pullRequest(number: $PR_NUMBER) { reviewThreads(first: 100${cursor_arg}) { pageInfo { hasNextPage endCursor } nodes { isResolved path line startLine comments(first: 100) { nodes { author { login } body } } } } } } }"

        local response
        response=$(gh api graphql -f query="$query")

        local threads
        threads=$(echo "$response" | jq '.data.repository.pullRequest.reviewThreads.nodes')
        all_threads=$(echo "$all_threads" | jq ". + $threads")

        has_next=$(echo "$response" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage')
        cursor=$(echo "$response" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor')

        if [ "$cursor" = "null" ]; then
            has_next=false
        fi
    done

    echo "$all_threads"
}

# Fetch all threads
ALL_THREADS=$(fetch_all_threads)

# Filter unresolved threads and output XML
echo "$ALL_THREADS" | jq -r '.[] | select(.isResolved == false) |
    "    <thread>",
    "      <file>" + (.path // "unknown") + "</file>",
    (if .line != null then "      <line>" + (.line | tostring) + "</line>" else "" end),
    (if .startLine != null then "      <start_line>" + (.startLine | tostring) + "</start_line>" else "" end),
    "      <comments>",
    (.comments.nodes[] |
        "        <comment>",
        "          <author>" + .author.login + "</author>",
        "          <body><![CDATA[" + .body + "]]></body>",
        "        </comment>"
    ),
    "      </comments>",
    "    </thread>"
' | grep -v '^$'

echo '  </threads>'
echo '</pr_unresolved_comments>'
