# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Fixed

- Fixed issue where certain characters (like brackets) wouldn't be displayed in the logs output
  when following the experiment with `--timeout -1`.

## [v0.13.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.13.0) - 2023-03-09

### Changed

- A GitHub personal access token is no-longer required for public repos.

## [v0.12.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.12.0) - 2023-03-08

### Added

- Added three options: `--replicas` (int), `--leader-selection` (flag), and `--host-networking` (flag) that give you the ability to run [distributed batch jobs](https://beaker-docs.apps.allenai.org/distributed-training.html#batch-jobs).

### Changed

- You can now use any image as long as it comes with `bash`. `conda` is no longer a requirement.

## [v0.11.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.11.0) - 2023-03-07

### Added

- Added the ability to override how packages/dependencies are installed via
  the option `--install`.

## [v0.10.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.10.0) - 2023-03-07

### Changed

- You can now specify the `--cluster` option as a wildcard, e.g. `--cluster ai2/*-cirrascale`.

## [v0.9.4](https://github.com/allenai/beaker-gantry/releases/tag/v0.9.4) - 2023-03-07

### Fixed

- Improved how `--beaker-image` option is resolved.

## [v0.9.3](https://github.com/allenai/beaker-gantry/releases/tag/v0.9.3) - 2023-03-02

### Fixed

- Fixed issue where cirrascale NFS would be potentially be attached to non-cirrascale machines when `--clusters` is left unspecified.
- Fixed issue where Gantry would not use a conda `environment.yaml` file by default (only found file with `.yml` extension).

## [v0.9.2](https://github.com/allenai/beaker-gantry/releases/tag/v0.9.2) - 2023-03-02

### Changed

- Loosened version requirements on some dependencies.

## [v0.9.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.9.1) - 2023-02-13

### Changed

- Fix NFS location issue.

## [v0.9.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.9.0) - 2023-02-10

### Changed

- You can now set the priority of your jobs via `--priority`.
- By default if you don't specify a cluster and priority, jobs will be submitted to all clusters under preemptible priority.

## [v0.8.2](https://github.com/allenai/beaker-gantry/releases/tag/v0.8.2) - 2023-01-19

### Added

- Added `--env` and `--env-secret` options for adding environment variables to your Beaker experiments.

## [v0.8.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.8.1) - 2022-09-30

### Fixed

- Fixed an issue when using a custom Docker image where Gantry would fail if the working directory of the image was non-empty.

## [v0.8.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.8.0) - 2022-09-16

### Fixed

- Fixed issue where Python version was too specific for Conda. Now we only specify the major and minor version.

## [v0.7.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.7.0) - 2022-06-16

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
