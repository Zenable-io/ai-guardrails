#!/usr/bin/env bash
set -euo pipefail

# Script to mark a PR thread as addressed by a specific commit OR with a custom comment
# Usage: ./mark-addressed.sh <PR_NUMBER> <FILE_PATH> <LINE_NUMBER|-> <COMMIT_HASH|--comment BODY> [THREAD_INDEX]

PR_NUMBER="${1:-}"
FILE_PATH="${2:-}"
LINE_NUMBER="${3:-}"
PARAM4="${4:-}"

# Parse parameters to support both commit hash and custom comment modes
COMMIT_HASH=""
COMMENT_BODY=""
THREAD_INDEX="1"  # Default to first thread if multiple match

if [ "$PARAM4" = "-c" ] || [ "$PARAM4" = "--comment" ]; then
    # Custom comment mode: -c "comment text" [thread_index]
    COMMENT_BODY="${5:-}"
    THREAD_INDEX="${6:-1}"
    if [ -z "$COMMENT_BODY" ]; then
        echo "ERROR: --comment requires a comment body" >&2
        exit 1
    fi
else
    # Commit hash mode: commit_hash [thread_index]
    COMMIT_HASH="$PARAM4"
    THREAD_INDEX="${5:-1}"
fi

if [ -z "$PR_NUMBER" ] || [ -z "$FILE_PATH" ] || [ -z "$LINE_NUMBER" ] || { [ -z "$COMMIT_HASH" ] && [ -z "$COMMENT_BODY" ]; }; then
    cat >&2 <<EOF
Usage: $0 <PR_NUMBER> <FILE_PATH> <LINE_NUMBER or "-"> <COMMIT_HASH|--comment BODY> [THREAD_INDEX]

Examples:
  # Mark thread at specific line with commit hash
  $0 2782 packages/zenable_utils/src/zenable_utils/bedrock.py 118 abc123f

  # Mark file-level thread (no specific line) with commit hash
  $0 2782 packages/zenable_utils/src/zenable_utils/bedrock.py - abc123f

  # Mark second file-level thread if multiple exist
  $0 2782 packages/zenable_utils/src/zenable_utils/bedrock.py - abc123f 2

  # Reply to thread with custom comment (no commit)
  $0 2782 packages/zenable_utils/src/zenable_utils/bedrock.py 118 --comment "This is intentional because..."

  # Reply to file-level thread with custom comment
  $0 2782 packages/zenable_utils/src/zenable_utils/bedrock.py - -c "Good catch, but no changes needed"

  # Reply to specific thread when multiple match
  $0 2782 packages/zenable_utils/src/zenable_utils/bedrock.py - --comment "Acknowledged" 2
EOF
    exit 1
fi

# Get repo owner and name
REPO_INFO=$(gh repo view --json owner,name)
OWNER=$(echo "$REPO_INFO" | jq -r '.owner.login')
REPO=$(echo "$REPO_INFO" | jq -r '.name')

# Create comment body based on mode
if [ -n "$COMMIT_HASH" ]; then
    # Format commit hash (support short or full)
    SHORT_HASH=$(echo "$COMMIT_HASH" | cut -c1-7)
    FINAL_COMMENT_BODY="<h1>Automated Message</h1>\\n\\nAddressed in ${SHORT_HASH}"
    MODE_DESC="commit ${SHORT_HASH}"
else
    # Use custom comment body
    FINAL_COMMENT_BODY="$COMMENT_BODY"
    MODE_DESC="custom comment"
fi

# Determine if we're searching by line number or not
if [ "$LINE_NUMBER" = "-" ] || [ "$LINE_NUMBER" = "0" ]; then
    SEARCH_BY_LINE=false
    echo "Marking file-level thread on ${FILE_PATH} with ${MODE_DESC}..." >&2
else
    SEARCH_BY_LINE=true
    echo "Marking ${FILE_PATH}:${LINE_NUMBER} with ${MODE_DESC}..." >&2
fi

# Function to fetch all review threads and find the matching one(s)
find_thread_ids() {
    local cursor=""
    local has_next=true
    local all_thread_ids=()

    while [ "$has_next" = "true" ]; do
        local cursor_arg=""
        if [ -n "$cursor" ]; then
            cursor_arg=", after: \"$cursor\""
        fi

        local query="{ repository(owner: \"$OWNER\", name: \"$REPO\") { pullRequest(number: $PR_NUMBER) { reviewThreads(first: 100${cursor_arg}) { pageInfo { hasNextPage endCursor } nodes { id path line startLine isResolved } } } } }"

        local response
        response=$(gh api graphql -f query="$query")

        # Find threads matching criteria
        local thread_ids
        if [ "$SEARCH_BY_LINE" = "true" ]; then
            # Search for threads with specific line number
            thread_ids=$(echo "$response" | jq -r --arg path "$FILE_PATH" --arg line "$LINE_NUMBER" '.data.repository.pullRequest.reviewThreads.nodes[] | select(.path == $path and (.line == ($line | tonumber) or .startLine == ($line | tonumber)) and .isResolved == false) | .id')
        else
            # Search for file-level threads (no line number)
            thread_ids=$(echo "$response" | jq -r --arg path "$FILE_PATH" '.data.repository.pullRequest.reviewThreads.nodes[] | select(.path == $path and .line == null and .startLine == null and .isResolved == false) | .id')
        fi

        # Add found IDs to array
        while IFS= read -r id; do
            if [ -n "$id" ]; then
                all_thread_ids+=("$id")
            fi
        done <<< "$thread_ids"

        has_next=$(echo "$response" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.hasNextPage')
        cursor=$(echo "$response" | jq -r '.data.repository.pullRequest.reviewThreads.pageInfo.endCursor')

        if [ "$cursor" = "null" ]; then
            has_next=false
        fi
    done

    # Return all found thread IDs (one per line)
    printf '%s\n' "${all_thread_ids[@]}"
}

# Find matching thread IDs
mapfile -t THREAD_IDS < <(find_thread_ids)

if [ "${#THREAD_IDS[@]}" -eq 0 ]; then
    if [ "$SEARCH_BY_LINE" = "true" ]; then
        echo "ERROR: Could not find unresolved thread for ${FILE_PATH}:${LINE_NUMBER}" >&2
    else
        echo "ERROR: Could not find unresolved file-level thread for ${FILE_PATH}" >&2
    fi
    exit 1
fi

# If multiple threads found, show them and use the specified index
if [ "${#THREAD_IDS[@]}" -gt 1 ]; then
    echo "Found ${#THREAD_IDS[@]} matching unresolved threads:" >&2
    for i in "${!THREAD_IDS[@]}"; do
        echo "  [$((i+1))] ${THREAD_IDS[$i]}" >&2
    done

    if [ "$THREAD_INDEX" -gt "${#THREAD_IDS[@]}" ] || [ "$THREAD_INDEX" -lt 1 ]; then
        echo "ERROR: Thread index $THREAD_INDEX is out of range (1-${#THREAD_IDS[@]})" >&2
        exit 1
    fi

    THREAD_ID="${THREAD_IDS[$((THREAD_INDEX-1))]}"
    echo "Using thread #${THREAD_INDEX}: ${THREAD_ID}" >&2
else
    THREAD_ID="${THREAD_IDS[0]}"
    echo "Found thread ID: ${THREAD_ID}" >&2
fi

# Post comment to the thread using GraphQL mutation
MUTATION="mutation {
  addPullRequestReviewThreadReply(input: {
    pullRequestReviewThreadId: \"${THREAD_ID}\",
    body: \"${FINAL_COMMENT_BODY}\"
  }) {
    comment {
      id
    }
  }
}"

response=$(gh api graphql -f query="$MUTATION")

# Check if the mutation was successful
if echo "$response" | jq -e '.data.addPullRequestReviewThreadReply.comment.id' > /dev/null 2>&1; then
    if [ "$SEARCH_BY_LINE" = "true" ]; then
        echo "Successfully posted comment to thread at ${FILE_PATH}:${LINE_NUMBER}" >&2
    else
        echo "Successfully posted comment to file-level thread on ${FILE_PATH}" >&2
    fi
else
    echo "ERROR: Failed to post comment. Response: $response" >&2
    exit 1
fi
