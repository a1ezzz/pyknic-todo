#!/usr/bin/env bash
set -euo pipefail

# Ensure the script operates from the repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

# Validate command-line parameters
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    echo "Usage: $0 <github_token> <twine_token>" >&2
    echo "Example: $0 ghp_xxxx pypi-yyyy" >&2
    exit 0
fi

if [ "$#" -gt 2 ]; then
    echo "Error: Too many arguments." >&2
    echo "Usage: $0 <github_token> <twine_token>" >&2
    exit 1
fi

GITHUB_TOKEN="${1:-${GITHUB_TOKEN:-}}"
TWINE_TOKEN="${2:-${TWINE_TOKEN:-${TWINE_PASSWORD:-}}}"

if [ -z "$GITHUB_TOKEN" ] || [ -z "$TWINE_TOKEN" ]; then
    echo "Error: Both github_token and twine_token must be provided." >&2
    echo "Usage: $0 <github_token> <twine_token>" >&2
    exit 1
fi

# Locate Python interpreter and twine
if [ -f "${REPO_ROOT}/.venv/bin/python" ]; then
    PYTHON="${REPO_ROOT}/.venv/bin/python"
else
    PYTHON="$(command -v python3 || command -v python || true)"
fi

if [ -z "$PYTHON" ] || [ ! -x "$PYTHON" ]; then
    echo "Error: Python interpreter not found." >&2
    exit 1
fi

if [ -x "${REPO_ROOT}/.venv/bin/twine" ]; then
    TWINE="${REPO_ROOT}/.venv/bin/twine"
elif command -v twine &>/dev/null; then
    TWINE="twine"
elif "$PYTHON" -m twine --version &>/dev/null; then
    TWINE="${PYTHON} -m twine"
else
    echo "Error: 'twine' is not found. Please install twine (e.g. .venv/bin/pip install twine)." >&2
    exit 1
fi

# 1. Check that there are no uncommitted changes in the git repository
if [ -n "$(git status --porcelain -uno)" ]; then
    echo "Error: Working tree has uncommitted changes. Please commit or stash them first." >&2
    exit 1
fi

# 2. Check that the current branch starts with "release/"
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || git symbolic-ref --short HEAD 2>/dev/null || true)
if [ -z "$CURRENT_BRANCH" ]; then
    echo "Error: Could not determine current branch (detached HEAD?)." >&2
    exit 1
fi

if [[ "$CURRENT_BRANCH" != release/* ]]; then
    echo "Error: Current branch must start with 'release/' (current branch: '${CURRENT_BRANCH}')." >&2
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

PUSH_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${REPO_PATH}.git"

# 3. Check that current branch HEAD does not differ from the remote branch on GitHub
LOCAL_HEAD=$(git rev-parse HEAD)
REMOTE_HEAD=$(git ls-remote "${PUSH_URL}" "refs/heads/${CURRENT_BRANCH}" 2>/dev/null | awk '{print $1}' || true)

if [ -z "$REMOTE_HEAD" ]; then
    echo "Error: Branch '${CURRENT_BRANCH}' does not exist on GitHub repository '${REPO_PATH}'." >&2
    exit 1
fi

if [ "$LOCAL_HEAD" != "$REMOTE_HEAD" ]; then
    echo "Error: Current branch HEAD (${LOCAL_HEAD}) differs from GitHub HEAD (${REMOTE_HEAD}) on '${CURRENT_BRANCH}'." >&2
    exit 1
fi

# 4. Get current package version
get_package_version() {
    local ver=""
    if [ -n "${PYTHON:-}" ] && [ -x "${PYTHON}" ]; then
        ver=$("${PYTHON}" -c "
try:
    import pyknic_todo
    print(pyknic_todo.__version__)
except Exception:
    pass
" 2>/dev/null || true)
    fi

    if [ -z "$ver" ] && [ -f "setup.cfg" ]; then
        local attr_spec
        attr_spec=$(sed -n -E "s/^[[:space:]]*version[[:space:]]*=[[:space:]]*attr:[[:space:]]*['\"]?([^'\"[:space:]]+)['\"]?/\1/p" setup.cfg)
        if [ -n "$attr_spec" ]; then
            local mod_path="${attr_spec%.*}"
            local var_name="${attr_spec##*.}"
            local mod_dir="${mod_path//.//}"
            for candidate in "${mod_dir}/__init__.py" "${mod_dir}.py" "src/${mod_dir}/__init__.py" "src/${mod_dir}.py"; do
                if [ -f "$candidate" ]; then
                    ver=$(sed -n -E "s/^[[:space:]]*${var_name}[[:space:]]*=[[:space:]]*['\"]([^'\"]+)['\"]/\1/p" "$candidate" | head -n 1)
                    break
                fi
            done
        fi
    fi

    echo "$ver"
}

PACKAGE_VERSION=$(get_package_version)
if [ -z "$PACKAGE_VERSION" ]; then
    echo "Error: Failed to determine package version." >&2
    exit 1
fi

TAG="v${PACKAGE_VERSION}"

# 5. Check that tag "v<version>" does not exist on GitHub
REMOTE_TAG_REF=$(git ls-remote "${PUSH_URL}" "refs/tags/${TAG}" 2>/dev/null | awk '{print $1}' || true)
if [ -n "$REMOTE_TAG_REF" ]; then
    echo "Error: Tag '${TAG}' already exists on GitHub repository '${REPO_PATH}'." >&2
    exit 1
fi

TAG_HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/${REPO_PATH}/git/ref/tags/${TAG}")

if [ "$TAG_HTTP_STATUS" -eq 200 ]; then
    echo "Error: Tag '${TAG}' already exists on GitHub repository '${REPO_PATH}'." >&2
    exit 1
elif [ "$TAG_HTTP_STATUS" -ne 404 ]; then
    echo "Error: Failed to check tag '${TAG}' via GitHub API (HTTP status: ${TAG_HTTP_STATUS})." >&2
    exit 1
fi

if git rev-parse --verify "refs/tags/${TAG}" >/dev/null 2>&1; then
    echo "Error: Local tag '${TAG}' already exists." >&2
    exit 1
fi

# 6. Display summary and ask for confirmation before any modifications
cat <<EOF

==================================================
Public release summary:
  GitHub repository:      ${REPO_PATH}
  Current branch:         ${CURRENT_BRANCH}
  Branch HEAD:            ${LOCAL_HEAD}
  Package version:        ${PACKAGE_VERSION}
  Git tag to create:      ${TAG}
  GitHub release:         ${TAG} (marked as pre-release)
  Build targets:          sdist, bdist_wheel
  Target index:           PyPI (via twine)

Actions to be performed:
  1. Create annotated git tag '${TAG}' and push it to GitHub
  2. Create GitHub release card for '${TAG}' with pre-release flag
  3. Build distribution packages (sdist and bdist_wheel)
  4. Upload distribution packages to PyPI via twine
==================================================

EOF

read -r -p "Do you want to proceed with the release? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[Yy]([Ee][Ss])?$ ]]; then
    echo "Operation aborted by user."
    exit 0
fi

# 7. Create new tag "v<version>" and push to GitHub
echo "Creating git tag '${TAG}'..."
git tag -a "${TAG}" -m "Release ${TAG}"

echo "Pushing tag '${TAG}' to GitHub..."
git push "${PUSH_URL}" "refs/tags/${TAG}"

# 8. Create GitHub release card marked as pre-release
echo "Creating GitHub pre-release card..."
RELEASE_TITLE="Release ${TAG}"
RELEASE_NOTES="Pre-release ${TAG}"

if command -v jq &>/dev/null; then
    RELEASE_PAYLOAD=$(jq -n \
        --arg tag "${TAG}" \
        --arg target "${CURRENT_BRANCH}" \
        --arg name "${RELEASE_TITLE}" \
        --arg body "${RELEASE_NOTES}" \
        '{tag_name: $tag, target_commitish: $target, name: $name, body: $body, draft: false, prerelease: true, generate_release_notes: true}')
else
    RELEASE_PAYLOAD=$("${PYTHON}" -c '
import json, sys
print(json.dumps({
    "tag_name": sys.argv[1],
    "target_commitish": sys.argv[2],
    "name": sys.argv[3],
    "body": sys.argv[4],
    "draft": False,
    "prerelease": True,
    "generate_release_notes": True
}))' "${TAG}" "${CURRENT_BRANCH}" "${RELEASE_TITLE}" "${RELEASE_NOTES}")
fi

RELEASE_RESPONSE=$(curl -s -X POST \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    -d "${RELEASE_PAYLOAD}" \
    "https://api.github.com/repos/${REPO_PATH}/releases")

if command -v jq &>/dev/null; then
    RELEASE_URL=$(echo "${RELEASE_RESPONSE}" | jq -r '.html_url // empty')
else
    RELEASE_URL=$(echo "${RELEASE_RESPONSE}" | "${PYTHON}" -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get("html_url", ""))
except Exception:
    pass')
fi

if [ -z "${RELEASE_URL}" ] || [ "${RELEASE_URL}" = "null" ]; then
    echo "Error: Failed to create GitHub release card." >&2
    echo "GitHub API response: ${RELEASE_RESPONSE}" >&2
    exit 1
fi

echo "GitHub release created successfully: ${RELEASE_URL}"

# 9. Build sdist and bdist_wheel
echo "Cleaning old build artifacts..."
rm -rf dist/ build/

echo "Building sdist and bdist_wheel..."
"${PYTHON}" setup.py sdist bdist_wheel

if [ ! -d "dist" ] || [ -z "$(ls -A dist)" ]; then
    echo "Error: Build failed; dist/ directory is empty." >&2
    exit 1
fi

echo "Checking package distributions with twine..."
"${TWINE}" check dist/*

# 10. Upload package to PyPI via twine
echo "Uploading package to PyPI via twine..."
TWINE_USERNAME="__token__" TWINE_PASSWORD="${TWINE_TOKEN}" "${TWINE}" upload --non-interactive dist/*

echo "Public release completed successfully!"
