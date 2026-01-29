<div align="center">
<br>
<img src="https://raw.githubusercontent.com/allenai/beaker-py/main/docs/source/_static/beaker-500px-transparent.png" width="200"/>
<br>
<h1>Beaker Gantry</h1>
<p>Gantry is a CLI that streamlines running experiments in <a href="https://beaker.org">Beaker</a>.</p>
<hr/>
<!-- TODO: Add badges once this is open source -->
<a href="https://github.com/allenai/beaker-gantry/actions">
    <img alt="CI" src="https://github.com/allenai/beaker-gantry/actions/workflows/main.yml/badge.svg">
</a>
<a href="https://pypi.org/project/beaker-gantry/">
    <img alt="PyPI" src="https://img.shields.io/pypi/v/beaker-gantry">
</a>
<a href="https://github.com/allenai/beaker-gantry/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/github/license/allenai/beaker-gantry.svg?color=blue&cachedrop">
</a>
<br/><br/>
</div>

<!-- begin intro -->
![2025-07-18 12 49 12](https://github.com/user-attachments/assets/82fa93ae-f512-4e76-ab95-95a535515e5b)


⚡️*Easy to use*

- **No Docker required!** 🚫 🐳
- No writing Beaker YAML experiment specs.
- Easy setup.
- Simple CLI.

🏎  *Fast*

- Fire off Beaker experiments from your laptop instantly!
- No local image build or upload.

🪶 *Lightweight*

- Pure Python (built on top of [beaker](https://github.com/allenai/beaker)'s Python client).
- Minimal dependencies.

### Who is this for?

Gantry is for both new and seasoned Beaker users who need to run batch jobs (as opposed to interactive sessions) from a rapidly changing repository, especially Python-based jobs.

*Without* Gantry, this workflow usually looks like this:

1. Add a Dockerfile to your repository.
2. Build the Docker image locally.
3. Push the Docker image to Beaker.
4. Write a YAML Beaker experiment spec that points to the image you just uploaded.
5. Submit the experiment spec.
6. Make changes and repeat from step 2.

This requires experience with Docker, experience writing Beaker experiment specs, and a fast and reliable internet connection.

*With* Gantry, on the other hand, that same workflow simplifies down to this:

1. (Optional) Write a `pyproject.toml`/`setup.py` file, a PIP `requirements.txt` file, a or conda `environment.yml` file to specify your Python environment.
2. Commit and push your changes.
3. Submit and track a Beaker experiment with the `gantry run` command.
4. Make changes and repeat from step 2.
<!-- end intro -->

## In this README

- 💾 **[Installing](#installing)**
- 🚀 **[Quick start](#quick-start)**
- ❓ **[FAQ](#faq)**

### Additional info

#### 👋 *Examples*

- [Savings results / metrics from an experiment](./examples/metrics)

#### 💻 *For developers*

- [CHANGELOG](https://github.com/allenai/beaker-gantry/blob/main/CHANGELOG.md)
- [CONTRIBUTING](https://github.com/allenai/beaker-gantry/blob/main/CONTRIBUTING.md)

<!-- begin install -->
## Installing

### Installing with `pip`

Gantry is available [on PyPI](https://pypi.org/project/gantry/). Just run

```bash
pip install beaker-gantry
```

### Installing globally with `uv`

Gantry can be installed and made available on the PATH using [uv](https://docs.astral.sh/uv/):

```bash
uv tool install beaker-gantry
```

With this command, beaker-gantry is automatically installed to an isolated virtual environment.

### Installing from source

To install Gantry from source, first clone [the repository](https://github.com/allenai/beaker-gantry):

```bash
git clone https://github.com/allenai/beaker-gantry.git
cd beaker-gantry
```

Then run

```bash
pip install -e .
```
<!-- end install -->
<!-- begin quickstart -->
## Quick start

### One-time setup

1. **Create and clone your repository.**

    If you haven't already done so, create a GitHub repository for your project and clone it locally.
    **Every `gantry` command you run must be invoked from the root directory of your repository.**

2. **Configure Gantry.**

    If you've already configured the [Beaker command-line client](https://github.com/allenai/beaker/), Gantry will
    find and use the existing configuration file (usually located at `$HOME/.beaker/config.yml`).
    Otherwise just set the environment variable `BEAKER_TOKEN` to your Beaker [user token](https://beaker.org/user).

    Some gantry settings can also be specified in a `pyproject.toml` file under the section `[tool.gantry]`. For now those settings are:

    1. `workspace` - The default Beaker workspace to use.
    2. `gh_token_secret` - The name of the Beaker secret with your GitHub API token.
    3. `budget` - The default Beaker budget to use.
    4. `log_level` - The (local) Python log level. Defaults to "warning".
    5. `quiet` - A boolean. If true the gantry logo won't be displayed on the command line.

    For example:

    ```toml
    # pyproject.toml
    [tool.gantry]
    workspace = "ai2/my-default-workspace"
    gh_token_secret = "GITHUB_TOKEN"
    budget = "ai2/my-teams-budget"
    log_level = "warning"
    quiet = false
    ```

    The first time you call `gantry run ...` you'll also be prompted to provide a [GitHub personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token) with the `repo` scope if your repository is private. This allows Gantry to clone your private repository when it runs in Beaker. You don't have to do this just yet (Gantry will prompt you for it), but if you need to update this token later you can use the `gantry config set-gh-token` command.

3. (Optional) **Specify your Python environment.**

    Typically you'll have to create one of several different files to specify your Python environment. There are three widely used options:

    1. A [`pyproject.toml`](https://pip.pypa.io/en/stable/reference/build-system/pyproject-toml/) or [`setup.py`](https://docs.python.org/3/distutils/introduction.html#a-simple-example) file.
    2. A PIP [`requirements.txt`](https://pip.pypa.io/en/stable/user_guide/#requirements-files) file.
    3. A conda [`environment.yml`](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#create-env-file-manually) file.

    Gantry will automatically find and use these files to reconstruct your Python environment at runtime.
    Alternatively you can provide a custom Python install command with the `--install` option to `gantry run`, or skip the Python setup completely with `--no-python`.

### Submit your first experiment with Gantry

Let's spin up a Beaker experiment that just prints "Hello, World!" from Python.

First make sure you've committed *and* pushed all changes so far in your repository.
Then (from the root of your repository) run:

```bash
gantry run --show-logs -- python -c 'print("Hello, World!")'
```

*❗Note: Everything after the `--` is the command + arguments you want to run on Beaker. It's necessary to include the `--` if any of your arguments look like options themselves (like `-c` in this example) so gantry can differentiate them from its own options.*

In this case we didn't request any GPUs nor a specific cluster, so this could run on any Beaker cluster.
We can use the `--gpu-type` and `--gpus` options to get GPUs. For example:

```bash
gantry run --show-logs --gpu-type=h100 --gpus=1 -- python -c 'print("Hello, World!")'
```

Or we can use the `--cluster` option to request clusters by their name or aliases. For example:

```bash
gantry run --show-logs --cluster=ai2/jupiter --gpus=1 -- python -c 'print("Hello, World!")'
```

Try `gantry run --help` to see all of the available options.
<!-- end quickstart -->
<!-- begin faq -->
## FAQ

### Can I use my own Docker/Beaker image?
<details>
<summary>Click to expand 💬</summary>

You sure can! Just set the `--beaker-image TEXT` or `--docker-image TEXT` option.
Gantry can use any image that has bash, curl, and git installed.

If your image comes with a Python environment that you want gantry to use, add the flag `--system-python`.
For example:

```bash
gantry run --show-logs --docker-image='python:3.10' --system-python -- python --version
```

</details>

### Will Gantry work for GPU experiments?
<details>
<summary>Click to expand 💬</summary>

Absolutely! This was the main use-case Gantry was developed for. Just set the `--gpus INT` option for `gantry run` to the number of GPUs you need, and optionally `--gpu-type TEXT` (e.g. `--gpu-type=h100`).
</details>

### How can I save results or metrics from an experiment?
<details>
<summary>Click to expand 💬</summary>

By default Gantry uses the `/results` directory on the image as the location of the results dataset, which will also be set as the environment variable `RESULTS_DIR`.
That means that everything your experiment writes to this directory will be persisted as a Beaker dataset when the experiment finalizes.
And you can also attach metrics in Beaker for your experiment by writing a JSON file called `metrics.json` to the results directory, or by calling the function `gantry.api.write_metrics()` from within your experiment.
</details>

### How can I see the Beaker experiment spec that Gantry uses?
<details>
<summary>Click to expand 💬</summary>

You can use the `--dry-run` option with `gantry run` to see what Gantry will submit without actually submitting an experiment.
You can also use `--save-spec PATH` in combination with `--dry-run` to save the actual experiment spec to a YAML file.
</details>

### How can I update Gantry's GitHub token?
<details>
<summary>Click to expand 💬</summary>

Use the command `gantry config set-gh-token`.
</details>

### How can I attach Beaker datasets to an experiment?
<details>
<summary>Click to expand 💬</summary>

Use the `--dataset` option for `gantry run`. For example:

```bash
gantry run --show-logs --dataset='petew/squad-train:/input-data' -- ls /input-data
```
</details>

### How can I attach a WEKA bucket to an experiment?
<details>
<summary>Click to expand 💬</summary>

Use the `--weka` option for `gantry run`. For example:

```bash
gantry run --show-logs --weka='oe-training-default:/mount/weka' -- ls -l /mount/weka
```
</details>

### How can I run distributed multi-node batch jobs with Gantry?
<details>
<summary>Click to expand 💬</summary>

If you're using `torchrun` you can simply set the option `--replicas INT` along with the flag `--torchrun`.
Gantry will automatically configure your experiment and `torchrun` to run your command with all GPUs across all replicas.

For example:

```bash
gantry run \
  --show-logs \
  --gpus=8 \
  --gpu-type='h100' \
  --replicas=2 \
  --torchrun \
  --install 'uv pip install . torch numpy --torch-backend=cu129' \
  -- python -m gantry.all_reduce_bench
```

In general, the three options `--replicas INT`, `--leader-selection`, `--host-networking` used together give you the ability to run distributed batch jobs. See the [Beaker docs](https://beaker-docs.apps.allenai.org/experiments/distributed-training.html#batch-jobs) for more information.
Consider also setting `--propagate-failure`, `--propagate-preemption`, and `--synchronized-start-timeout TEXT` depending on your workload.

Here's a complete example using `torchrun` manually (without the `--torchrun` flag):

```bash
gantry run \
  --show-logs \
  --gpus=8 \
  --gpu-type='h100' \
  --replicas=2 \
  --leader-selection \
  --host-networking \
  --propagate-failure \
  --propagate-preemption \
  --synchronized-start-timeout='5m' \
  --install 'uv pip install . torch numpy --torch-backend=cu129' \
  --exec-method=bash \
  -- torchrun \
    '--nnodes="$BEAKER_REPLICA_COUNT:$BEAKER_REPLICA_COUNT"' \
    '--nproc-per-node="$BEAKER_ASSIGNED_GPU_COUNT"' \
    '--rdzv-id=12347' \
    '--rdzv-backend=static' \
    '--rdzv-endpoint="$BEAKER_LEADER_REPLICA_HOSTNAME:29400"' \
    '--node-rank="$BEAKER_REPLICA_RANK"' \
    '--rdzv-conf="read_timeout=420"' \
    -m gantry.all_reduce_bench
```

Note that we have environment variables like `BEAKER_REPLICA_COUNT` in the arguments to our `torchrun` command that we want to have expanded *at runtime*.
To accomplish this we do two things:
1. We wrap those arguments in single quotes to avoid expanding them locally.
2. We set `--exec-method=bash` to tell gantry to run our command and arguments with `bash -c`, which will do variable expansion.

Alternatively you could put your whole `torchrun` command into a script, let's call it `launch-torchrun.sh`, without single quotes around the arguments.
Then change your `gantry run` command like this:

```diff
 gantry run \
   --show-logs \
   --gpus=8 \
   --gpu-type='h100' \
   --replicas=2 \
   --leader-selection \
   --host-networking \
   --propagate-failure \
   --propagate-preemption \
   --synchronized-start-timeout='5m' \
   --install 'uv pip install . torch numpy --torch-backend=cu129' \
-  --exec-method='bash' \
-  -- torchrun \
-    '--nnodes="$BEAKER_REPLICA_COUNT:$BEAKER_REPLICA_COUNT"' \
-    '--nproc-per-node="$BEAKER_ASSIGNED_GPU_COUNT"' \
-    '--rdzv-id=12347' \
-    '--rdzv-backend=static' \
-    '--rdzv-endpoint="$BEAKER_LEADER_REPLICA_HOSTNAME:29400"' \
-    '--node-rank="$BEAKER_REPLICA_RANK"' \
-    '--rdzv-conf="read_timeout=420"' \
-    -m gantry.all_reduce_bench
+  -- ./launch-torchrun.sh
```
</details>

### How can I customize the Python setup steps?
<details>
<summary>Click to expand 💬</summary>

If gantry's default Python setup steps don't work for you, you can override them through the `--install TEXT` option with a custom command or shell script.
For example:

```bash
gantry run --show-logs --install='pip install -r custom_requirements.txt' -- echo "Hello, World!"
```
</details>

### Can I use conda like with older versions of gantry?
<details>
<summary>Click to expand 💬</summary>

Yes, you can still use conda if you wish by committing a conda `environment.yml` file to your repo or by simply specifying `--python-manager=conda`.
For example:

```bash
gantry run --show-logs --python-manager=conda -- which python
```
</details>

### Can I use gantry with non-Python workloads?
<details>
<summary>Click to expand 💬</summary>

Absolutely, just add the flag `--no-python` and optionally set `--install` or `--post-setup` to a custom command or shell script if you need custom setup steps.
</details>

### Can I use gantry to launch Beaker jobs from GitHub Actions?
<details>
<summary>Click to expand 💬</summary>

Yes, in fact this is a great way to utilize otherwise idle on-premise hardware, especially with short-running, preemptible jobs such as those you might launch to run unit tests that require accelerators.
To do this you should set up a Beaker API token as a GitHub Actions Secret, named `BEAKER_TOKEN`, in your repository.
Then copy and modify this workflow for your needs:

```yaml
name: Beaker

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

on:
  pull_request:
    branches:
      - main
  push:
    branches:
      - main

jobs:
  gpu_tests:
    name: GPU Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15
    env:
      BEAKER_TOKEN: ${{ secrets.BEAKER_TOKEN }}
      GANTRY_GITHUB_TESTING: 'true'  # force better logging for CI
      BEAKER_WORKSPACE: 'ai2/your-workspace'  # TODO: change this to your Beaker workspace
    steps:
      - uses: actions/checkout@v5
        with:
          ref: ${{ github.event.pull_request.head.sha }}  # check out PR head commit instead of merge commit

      - uses: astral-sh/setup-uv@v6
        with:
          python-version: '3.12'

      - name: install gantry
        run:
          uv tool install 'beaker-gantry>=3.1,<4.0'

      - name: Determine current commit SHA (pull request)
        if: github.event_name == 'pull_request'
        run: |
          echo "COMMIT_SHA=${{ github.event.pull_request.head.sha }}" >> $GITHUB_ENV
          echo "BRANCH_NAME=${{ github.head_ref }}" >> $GITHUB_ENV

      - name: Determine current commit SHA (push)
        if: github.event_name != 'pull_request'
        run: |
          echo "COMMIT_SHA=$GITHUB_SHA" >> $GITHUB_ENV
          echo "BRANCH_NAME=${{ github.ref_name }}" >> $GITHUB_ENV

      - name: launch job
        run: |
          exec gantry run \
            --show-logs \
            --yes \
            --workspace ${{ env.BEAKER_WORKSPACE }} \
            --description 'GitHub Actions GPU tests' \
            --ref ${{ env.COMMIT_SHA }} \
            --branch ${{ env.BRANCH_NAME }} \
            --priority normal \
            --preemptible \
            --gpus 1 \
            --gpu-type h100 \
            --gpu-type a100 \
            -- pytest -v tests/cuda_tests/  # TODO: change to your own command
```

Note that we use `exec gantry run ...` instead of just `gantry run`. This ensures that if GitHub Actions cancels the job, the SIGINT and SIGTERM signals will propagate to `gantry`, allowing it to clean up gracefully and cancel the running job on Beaker.
</details>

### Why "Gantry"?
<details>
<summary>Click to expand 💬</summary>

A gantry is a structure that's used, among other things, to lift containers off of ships. Analogously Beaker Gantry's purpose is to lift Docker containers (or at least the *management* of Docker containers) away from users.
</details>
<!-- end faq -->
