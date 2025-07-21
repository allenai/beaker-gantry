#!/bin/bash

set -e

TAG=$(python -c 'from gantry.version import VERSION; print("v" + VERSION)')

read -p "Creating new release for $TAG. Do you want to continue? [Y/n] " prompt
if ! [[ $prompt == "y" || $prompt == "Y" || $prompt == "yes" || $prompt == "Yes" ]]; then
    echo "Cancelled"
    exit 1
fi

python scripts/prepare_changelog.py

read -p "Changelog updated. Does it look right? [Y/n] " prompt
if ! [[ $prompt == "y" || $prompt == "Y" || $prompt == "yes" || $prompt == "Yes" ]]; then
    echo "Cancelled"
    exit 1
fi

echo "Creating new commit..."
git add -A
git commit -m "(chore) bump version to $TAG for release" || true && git push

echo "Creating new git tag $TAG..."
git tag "$TAG" -m "$TAG"
git push --tags

echo "All changes/tags pushed. GitHub Actions will handle the rest."
echo 'https://github.com/allenai/beaker-gantry/actions/workflows/main.yml'
