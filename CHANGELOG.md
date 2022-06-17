# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Changed

- `gantry run` will now live stream the logs for the experiment when `--timeout` is not 0.

## [v0.6.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.6.0) - 2022-06-10

### Added

- Added `--dataset` option for attaching input datasets to an experiment.
  For example: `gantry run --dataset 'petew/squad-train:/input-data' -- ls /input-data`

## [v0.5.2](https://github.com/allenai/beaker-gantry/releases/tag/v0.5.2) - 2022-06-10

### Changed

- `beaker-py` v1.4.1 or newer now required.

## [v0.5.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.5.1) - 2022-06-09

### Changed

- `beaker-py` v1.4 or newer now required to make use of `Beaker.session()` for performance.

## [v0.5.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.5.0) - 2022-06-03

### Added

- Added a command `gantry config set-gh-token` for setting or updating your GitHub personal access token for a Beaker workspace.

## [v0.4.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.4.0) - 2022-05-23

### Added

- Added the `--venv` option. Use this to specify an existing conda environment on your image to use.

## [v0.3.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.3.1) - 2022-05-20

### Changed

- You can now overwrite an existing file with the `--save-spec` option. Pass `--yes` to avoid the confirmation prompt.

## [v0.3.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.3.0) - 2022-05-18

### Added

- NFS drive automatically attached when using cirrascale clusters.
- Added `--save-spec PATH` option to `beaker run` for saving the generated experiment spec to a YAML file.
- Added automatic upgrade checks. You'll get a warning message if your installation of gantry is out-of-date.
- Entrypoint now shows useful Python environment info from the entrypoint script.

## [v0.2.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.2.1) - 2022-05-16

### Changed

- Runtime, results, and metrics now printed at the end.

### Fixed

- Fixed the potential for a race condition when `gantry run` is called on the same workspace from multiple processes when creating a new entrypoint dataset, resulting in a `DatasetConflict` error.

## [v0.2.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.2.0) - 2022-05-16

### Added

- Added additional `--dry-run` output.
- Added `--yes` flag for skipping confirmation prompts.

### Changed

- Public workspaces are now allowed.
- Workspaces with multiple contributors are now allowed, but you'll be asked to confirm
  that it's okay.

## [v0.1.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.1.0) - 2022-05-13

### Added

- Added `gantry` CLI.
