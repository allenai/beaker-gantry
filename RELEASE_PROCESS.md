# GitHub Release Process

## Steps

1. Update the version in `gantry/version.py`.

3. Run the release script:

    ```bash
    ./scripts/release.sh
    ```

    This will commit the changes to the CHANGELOG and `version.py` files and then create a new tag in git
    which will trigger a workflow on GitHub Actions that handles the rest.

## Fixing a failed release

If for some reason the GitHub Actions release workflow failed with an error that needs to be fixed, you'll have to delete both the tag and corresponding release (if it made it that far) from GitHub.
Then repeat the steps above.
