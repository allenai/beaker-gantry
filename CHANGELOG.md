# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## [v1.4.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.4.0) - 2024-05-31

### Added

- Added `gantry completion ...` commands for configuring `gantry` shell autocompletion.

## [v1.3.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.3.0) - 2024-05-31

### Added

- Added `--tail` option to `gantry follow` to only tail the logs as opposed to dumping the entire history.

## [v1.2.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.2.0) - 2024-05-30

### Changed

- Changed what info is displayed by default from `gantry cluster util`. Now only a succinct summary is shown by default, but you can still get node details by adding the flag `--nodes`.
- Allow multiple `--status` options with `gantry list` command.

## [v1.1.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.1.0) - 2024-05-29

### Added

- Added `gantry list` command for listing gantry experiments.

### Fixed

- Improve handling of jobs that fail without an exit code.
- Improved output format of `gantry cluster *` commands.

### Removed

- Removed `gantry cluster allow-preemptible` and `gantry cluster disallow-preemptible` commands.

## [v1.0.1](https://github.com/allenai/beaker-gantry/releases/tag/v1.0.1) - 2024-05-24

### Fixed

- Fixed formatting in `gantry cluster` and `gantry config` commands.

## [v1.0.0](https://github.com/allenai/beaker-gantry/releases/tag/v1.0.0) - 2024-05-24

### Added

- Added `gantry stop` command.

## [v0.24.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.24.0) - 2024-05-21

### Added

- Added `--no-python` flag to skip setting up a Python environment entirely.
- Added `GANTRY_TASK_NAME` runtime environment variable, which will always match the `--task-name` argument.

### Changed

- Gantry no longer cancels an experiment on keyboard interrupt.

## [v0.23.2](https://github.com/allenai/beaker-gantry/releases/tag/v0.23.2) - 2024-05-16

### Fixed

- Don't automatically attach NFS to "jupiter" cluster.

## [v0.23.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.23.1) - 2024-05-14

### Changed

- Retry `git clone` a few times in the entrypoint script to be more robust to issues on the Jupiter cluster.

## [v0.23.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.23.0) - 2024-05-10

### Added

- Added `--preemptible` flag.

## [v0.22.4](https://github.com/allenai/beaker-gantry/releases/tag/v0.22.4) - 2024-04-30

### Added

- Added `--synchronized-start-timeout` option.

## [v0.22.3](https://github.com/allenai/beaker-gantry/releases/tag/v0.22.3) - 2024-04-24

### Added

- Added `--propagate-failure` flag.

## [v0.22.2](https://github.com/allenai/beaker-gantry/releases/tag/v0.22.2) - 2024-03-01

### Fixed

- Warn instead of fail when we can't preempt jobs.

## [v0.22.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.22.1) - 2024-02-28

### Fixed

- Don't consider default "ai2" account a workspace contributor.

## [v0.22.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.22.0) - 2024-02-28

### Added

- Added flag `--stop-preemptible` to `gantry run` for stopping all preemptible jobs on the cluster. This requires that your job is not preemptible and you've specified a single cluster.
- Added subcommands `gantry cluster allow-preemptible [CLUSTER]` and `gantry cluster disallow-preemptible [CLUSTER]`.

### Changed

- Won't prompt for name if `--yes` flag is given.

## [v0.21.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.21.0) - 2024-01-30

### Added

- Added `--budget` option (required).

## [v0.20.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.20.1) - 2023-12-15

### Fixed

- Changed how unique names are generated so always 2 characters plus 2 digits.

## [v0.20.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.20.0) - 2023-12-15

### Changed

- When you try to launch an experiment through `gantry` with a `--name` that already exists on Beaker, `gantry` will now add a few random characters to the end of the name instead of throwing an error.

## [v0.19.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.19.0) - 2023-09-08

### Added

- Added commands `gantry cluster list` and `gantry cluster util` for listing clusters and showing cluster utilization, respectively.

## [v0.18.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.18.0) - 2023-08-23

### Added

- Added `gantry follow [EXPERIMENT]` command for following the logs of a running experiment.

## [v0.17.2](https://github.com/allenai/beaker-gantry/releases/tag/v0.17.2) - 2023-07-21

### Fixed

- Provide a more useful error message when you pass a path to `--venv` and that path doesn't exist.

## [v0.17.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.17.1) - 2023-07-12

### Fixed

- Fixed bug when workspace permissions are `None`.

## [v0.17.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.17.0) - 2023-06-23

### Added

- Added `--hostname` constraint option.

## [v0.16.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.16.0) - 2023-05-22

### Added

- Added support for subpaths when attaching datasets. For example: `--dataset 'dataset-name:sub/path:/mount/location'`.

## [v0.15.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.15.1) - 2023-05-08

### Fixed

- Don't override existing `PYTHONPATH` entries.

## [v0.15.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.15.0) - 2023-05-08

### Added

- Added the `-m/--mount` option for mounting a host directory to experiments.

## [v0.14.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.14.1) - 2023-04-17

### Fixed

- Fixed a bug where some dependencies were not actually installed.

## [v0.14.0](https://github.com/allenai/beaker-gantry/releases/tag/v0.14.0) - 2023-04-17

### Added

- Added automatic support for `pyproject.toml` and `setup.cfg` files in addition to `setup.py`.

## [v0.13.1](https://github.com/allenai/beaker-gantry/releases/tag/v0.13.1) - 2023-03-20

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
