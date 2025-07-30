#!/usr/bin/env bash

set +x -eo pipefail

function confirm {
    read -rp "$1 [Y/n] " prompt
    if ! [[ $prompt == "y" || $prompt == "Y" || $prompt == "yes" || $prompt == "Yes" ]]; then
        echo "❯ Canceled."
        exit 1
    fi
}

echo "❯ Syncing local repo with remote..."
git pull > /dev/null
git tag -l | xargs git tag -d > /dev/null 2>&1
git fetch -t > /dev/null 2>&1

TAG=$(python -c 'from gantry.version import VERSION; print("v" + VERSION)')
export TAG

confirm "❯ Creating new release $TAG. Do you want to continue?"
python scripts/prepare_changelog.py
git add -A > /dev/null 2>&1
git commit -m "(chore) bump version to $TAG for release" > /dev/null 2>&1 || true && git push > /dev/null
git tag "$TAG" -m "$TAG" > /dev/null

echo "❯ Release notes preview:"
echo "------------------------"
python scripts/release_notes.py
echo "------------------------"
confirm "❯ Does this look right?"
git push --tags > /dev/null

echo "❯ All changes/tags pushed. GitHub Actions will handle the rest."
echo '❯ See: https://github.com/allenai/beaker-gantry/actions/workflows/main.yml'
