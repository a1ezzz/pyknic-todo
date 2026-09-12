#!/usr/bin/env bash
set -euo pipefail

# Ensure the script operates from the repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# Validate command-line arguments
if [ "$#" -ne 3 ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    echo "Usage: $0 <release_version> <test_version> [<github_token>]" >&2
    echo "Example: $0 0.1.0 0.2.0-dev ghp_xxxx" >&2
    exit 1
fi

RELEASE_VERSION="$1"
TEST_VERSION="$2"
GITHUB_TOKEN="${3:-${GITHUB_TOKEN}}"

if [ -z "$RELEASE_VERSION" ] || [ -z "$TEST_VERSION" ] || [ -z "$GITHUB_TOKEN" ]; then
    echo "Error: Parameters cannot be empty." >&2
    echo "Usage: $0 <release_version> <test_version> <github_token>" >&2
    exit 1
fi

# 1. Check that there are no uncommitted changes in the git repository
if [ -n "$(git status --porcelain -uno)" ]; then
    echo "Error: Working tree has uncommitted changes. Please commit or stash them first." >&2
    exit 1
fi

# 2. Check that test version ends with "-dev"
if [[ "$TEST_VERSION" != *-dev ]]; then
    echo "Error: Test version must end with '-dev' (received: '${TEST_VERSION}')." >&2
    exit 1
fi

# Determine GitHub repository owner and name from remote.origin.url
REMOTE_URL=$(git config --get remote.origin.url || true)
if [ -z "$REMOTE_URL" ]; then
    echo "Error: remote.origin.url is not set." >&2
    exit 1
fi

REPO_PATH=$(echo "$REMOTE_URL" | sed -E -e 's#^.*github\.com[:/]([^/]+/[^/\.]+)(\.git)?$#\1#')
if [ -z "$REPO_PATH" ]; then
    echo "Error: Failed to determine GitHub repository from remote URL: ${REMOTE_URL}" >&2
    exit 1
fi

# 3. Check that branch release/<release-version> does not exist in GitHub repository
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/${REPO_PATH}/branches/release/${RELEASE_VERSION}")

if [ "$HTTP_STATUS" -eq 200 ]; then
    echo "Error: Branch 'release/${RELEASE_VERSION}' already exists in GitHub repository '${REPO_PATH}'." >&2
    exit 1
elif [ "$HTTP_STATUS" -ne 404 ]; then
    echo "Error: Failed to check remote branch via GitHub API (HTTP status: ${HTTP_STATUS})." >&2
    exit 1
fi

RELEASE_BRANCH="release/${RELEASE_VERSION}"
FEATURE_BRANCH="feature/dev-release-${TEST_VERSION}"

# Check that local branches do not already exist
if git rev-parse --verify "refs/heads/${RELEASE_BRANCH}" >/dev/null 2>&1; then
    echo "Error: Local branch '${RELEASE_BRANCH}' already exists." >&2
    exit 1
fi

if git rev-parse --verify "refs/heads/${FEATURE_BRANCH}" >/dev/null 2>&1; then
    echo "Error: Local branch '${FEATURE_BRANCH}' already exists." >&2
    exit 1
fi

INIT_FILE="pyknic_todo/__init__.py"
if [ ! -f "$INIT_FILE" ]; then
    echo "Error: Version file '${INIT_FILE}' not found." >&2
    exit 1
fi

update_version() {
    local ver="$1"
    sed -i -E "s/__version__\s*=\s*['\"][^'\"]+['\"]/__version__ = \"${ver}\"/" "$INIT_FILE"
    if ! grep -q "__version__ = \"${ver}\"" "$INIT_FILE"; then
        echo "Error: Failed to update version in ${INIT_FILE} to '${ver}'." >&2
        exit 1
    fi
}

PUSH_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO_PATH}.git"

# Display summary and ask for user confirmation before executing any modifying actions
cat <<EOF

==================================================
Release automation plan:
  GitHub repository: ${REPO_PATH}
  Release version:   ${RELEASE_VERSION}
  Test/dev version:  ${TEST_VERSION}

Actions to be performed:
  1. Checkout 'main' and create branch '${RELEASE_BRANCH}'
  2. Set version to '${RELEASE_VERSION}' in ${INIT_FILE}, commit and push '${RELEASE_BRANCH}' to GitHub
  3. Checkout 'main' and create branch '${FEATURE_BRANCH}'
  4. Set version to '${TEST_VERSION}' in ${INIT_FILE}, commit and push '${FEATURE_BRANCH}' to GitHub
  5. Create Pull Request from '${FEATURE_BRANCH}' to 'main'
==================================================

EOF

read -r -p "Do you want to proceed with these actions? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[Yy]([Ee][Ss])?$ ]]; then
    echo "Operation aborted by user."
    exit 0
fi

# 4. Create release branch from main, update version, commit and push
echo "Switching to main branch..."
git checkout main
git pull origin main 2>/dev/null || git pull "${PUSH_URL}" main 2>/dev/null || true

echo "Creating release branch: ${RELEASE_BRANCH}..."
git checkout -b "${RELEASE_BRANCH}"
update_version "${RELEASE_VERSION}"
git add "${INIT_FILE}"
git commit -m "version updated to ${RELEASE_VERSION}"

echo "Pushing ${RELEASE_BRANCH} to GitHub..."
git push "${PUSH_URL}" "${RELEASE_BRANCH}:${RELEASE_BRANCH}"

# 5. Create feature branch from main, update version, commit and push
echo "Switching back to main branch..."
git checkout main

echo "Creating feature branch: ${FEATURE_BRANCH}..."
git checkout -b "${FEATURE_BRANCH}"
update_version "${TEST_VERSION}"
git add "${INIT_FILE}"
git commit -m "version updated to ${TEST_VERSION}"

echo "Pushing ${FEATURE_BRANCH} to GitHub..."
git push "${PUSH_URL}" "${FEATURE_BRANCH}:${FEATURE_BRANCH}"

# 6. Create pull request from feature branch to main and display the URL
echo "Creating Pull Request to main..."
if command -v jq &>/dev/null; then
    PR_PAYLOAD=$(jq -n \
        --arg title "Dev release ${TEST_VERSION}" \
        --arg head "${FEATURE_BRANCH}" \
        --arg base "main" \
        --arg body "Automated pull request for dev release ${TEST_VERSION}" \
        '{title: $title, head: $head, base: $base, body: $body}')
else
    PR_PAYLOAD=$(python3 -c '
import json, sys
print(json.dumps({
    "title": f"Dev release {sys.argv[1]}",
    "head": sys.argv[2],
    "base": "main",
    "body": f"Automated pull request for dev release {sys.argv[1]}"
}))' "${TEST_VERSION}" "${FEATURE_BRANCH}")
fi

PR_RESPONSE=$(curl -s -X POST \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    -d "${PR_PAYLOAD}" \
    "https://api.github.com/repos/${REPO_PATH}/pulls")

if command -v jq &>/dev/null; then
    PR_URL=$(echo "${PR_RESPONSE}" | jq -r '.html_url // empty')
else
    PR_URL=$(echo "${PR_RESPONSE}" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get("html_url", ""))
except Exception:
    pass')
fi

if [ -z "${PR_URL}" ] || [ "${PR_URL}" = "null" ]; then
    echo "Error: Failed to create Pull Request." >&2
    echo "GitHub API response: ${PR_RESPONSE}" >&2
    exit 1
fi

echo "Pull Request URL: ${PR_URL}"
