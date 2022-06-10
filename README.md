<div align="center">
<!-- TODO: Add logo -->
<br>
<img src="https://raw.githubusercontent.com/allenai/beaker-gantry/main/.github/gantry-logo-ascii.png"/>
<br>
<h1>Beaker Gantry</h1>
<p>Gantry streamlines running Python experiments in <a href="https://beaker.org">Beaker</a> by managing containers and boilerplate for you</p>
<hr/>
<!-- TODO: Add badges once this is open source -->
<a href="https://github.com/allenai/beaker-gantry/actions">
    <img alt="CI" src="https://github.com/allenai/beaker-gantry/workflows/Main/badge.svg?event=push&branch=main">
</a>
<a href="https://pypi.org/project/beaker-gantry/">
    <img alt="PyPI" src="https://img.shields.io/pypi/v/beaker-gantry">
</a>
<a href="https://github.com/allenai/beaker-gantry/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/github/license/allenai/beaker-gantry.svg?color=blue&cachedrop">
</a>
<br/>
</div>

⚡️*Easy to use*

- **No Docker required!** 🚫 🐳
- No writing YAML experiment specs.
- Easy setup.
- Simple CLI.

🏎  *Fast*

- Fire off Beaker experiments from your local computer instantly!
- No local image build or upload.

🪶 *Lightweight*

- Pure Python (built on top of [beaker-py](https://github.com/allenai/beaker-py)).
- Minimal dependencies.

### Who is this for?

Gantry is for both new and seasoned Beaker users who need to run Python batch jobs (as opposed to interactive sessions) from a rapidly changing repository.
Without Gantry, this workflow usually looks like this:

1. Add a Dockerfile to your repository.
2. Build the Docker image locally.
3. Push the Docker image to Beaker.
4. Write a YAML Beaker experiment spec that points to the image you just uploaded.
5. Submit the experiment spec.
6. Make changes and repeat from step 2.

This requires experience with Docker, experience writing Beaker experiment specs, and a fast and reliable internet connection (a luxury that some of us don't have, especially in the WFH era 🙃).

With Gantry, on the other hand, that same workflow simplifies down to this:

1. Write a conda `environment.yml` file, or simply a PIP `requirements.txt` and/or `setup.py` file.
2. Commit and push your changes.
3. Submit and track a Beaker experiment with the `gantry run` command.
4. Make changes and repeat from step 2.

## In this README

- 💾 **[Installing](#installing)**
- 🚀 **[Quick start](#quick-start)**
- 👓 **[Best practices](#best-practices)**
- ❓ **[FAQ](#faq)**

### Additional info

#### 👋 *Examples*

- [Savings results / metrics from an experiment](./examples/metrics)

#### 💻 *For developers*

- [CHANGELOG](https://github.com/allenai/beaker-gantry/blob/main/CHANGELOG.md)
- [CONTRIBUTING](https://github.com/allenai/beaker-gantry/blob/main/CONTRIBUTING.md)

## Installing

### Installing with `pip`

Gantry is available [on PyPI](https://pypi.org/project/gantry/). Just run

```bash
pip install beaker-gantry
```

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

## Quick start

### One-time setup

1. **Create and clone your repository.**

    If you haven't already done so, create a GitHub repository for your project and clone it locally.
    **Every `gantry` command you run must be invoked from the root directory of your repository.**

2. **Configure Gantry.**

    If you've already configured the [Beaker command-line client](https://github.com/allenai/beaker/), Gantry will 
    find and use the existing configuration file (usually located at `$HOME/.beaker/config.yml`).
    Otherwise just set the environment variable `BEAKER_TOKEN` to your Beaker [user token](https://beaker.org/user).

    The first time you call `gantry run ...` you'll also be prompted to provide a [GitHub personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token) with the `repo` scope. This allows Gantry to clone your private repository when it runs in Beaker. You don't have to do this just yet (Gantry will prompt you for it), but if you need to update this token later you can use the `gantry config set-gh-token` command.

3. **Specify your Python environment.**

    Lastly - and this is the most important part - you'll have to create one of several different files that specify your Python environment. There are three options:

    1. A conda [`environment.yml`](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#create-env-file-manually) file.
    2. A [`setup.py`](https://docs.python.org/3/distutils/introduction.html#a-simple-example) file.
    3. A PIP [`requirements.txt`](https://pip.pypa.io/en/stable/user_guide/#requirements-files) file.

    The first method is [the recommended approach](#use-conda), especially if you're already using conda.
    But it's perfectly okay to use a combination of these different approaches as well.
    This can be useful when, for example, you need to [use a CUDA-enabled version of PyTorch on Beaker but a CPU-only version locally](#how-do-i-use-a-cuda-enabled-version-of-pytorch-on-beaker-when-im-using-a-cpu-only-version-locally).

### Submit your first experiment with Gantry

Let's spin up a Beaker experiment that just prints "Hello, World!" from Python.

First make sure you've committed *and* pushed all changes so far in your repository.
Then (from the root of your repository) run:

```bash
gantry run --workspace {WORKSPACE} --cluster {CLUSTER} -- python -c 'print("Hello, World!")'
```

Just replace `{WORKSPACE}` with the name of your own Beaker [*private*](#use-your-own-private-beaker-workspace) workspace and `{CLUSTER}` with the name of the Beaker cluster you want to run on.

*❗Note: Everything after the `--` is the command + arguments you want to run on Beaker. It's necessary to include the `--` if any of your arguments look like options themselves (like `-c` in this example) so gantry can differentiate them from its own options.*

Try `gantry run --help` to see all of the available options.

## Best practices

### Use your own private Beaker workspace

Any authorized contributors to your workspace will have access to the secrets in your workspace, and Gantry needs to store your GitHub personal access token (PAT) as a secret in the workspace.
That's also why it's important to [limit the scope and lifetime of your GitHub token](#limit-the-scope-and-lifetime-of-your-github-token).

### Limit the scope and lifetime of your GitHub token

Your PAT only needs to have the `repo` scope and should have a short expiration time (e.g. 30 days).
This limits the harm a bad actor could cause if they were able to read your PAT from your Beaker workspace somehow.

### Use conda

Adding a [conda environment file](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#create-env-file-manually) will generally make your exact Python environment easier to reproduce, especially when you have platform-dependent requirements like PyTorch.
You don't necessarily need to write the `environment.yml` file manually either.
If you've already initialized a conda environment locally, you can just run:

```bash
conda env export --from-history
```

See [Exporting an Environment File Across Platforms](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#exporting-an-environment-file-across-platforms) for more details.

It's also okay to [use a combination of conda environment and PIP requirements files](#can-i-use-both-conda-environment-and-pip-requirements-files).

## FAQ

### Can I use my own Docker/Beaker image?

You sure can! Just set the `--beaker-image` or `--docker-image` flag.

Gantry can use any image that has bash and conda installed. This can be useful when you have dependencies that take a long time to download and build (like PyTorch).

In this case it works best if you build your image with a conda environment that already has your big dependencies installed. Then when you call `gantry run`, use the `--venv` option to tell Gantry to use that environment instead of creating a new conda environment in the container. You may also want to add a `requirements.txt` file to your repository that lists all of your dependencies (including PyTorch and anything else already installed in your image's conda environment) so Gantry can make sure the environment on the image is up-to-date when it runs.

For example, you could use one of our [pre-built PyTorch images](https://beaker.org/ws/ai2/fab/images?text=pytorch&sort=created:descending), such as [`ai2/pytorch1.11.0-cuda11.3-python3.9`](https://beaker.org/im/01G3S1CBQ0K832MCFDA77XQXFJ/details), like this:

```bash
gantry run \
    --beaker-image 'ai2/pytorch1.11.0-cuda11.3-python3.9' \
    --venv 'base' \
    --pip requirements.txt \
    -- python -c 'print("Hello, World!")'
```

### Will Gantry work for GPU experiments?

Absolutely! This was the main use-case Gantry was developed for. Just set the `--gpus` option for `gantry run` to the number of GPUs you need.
You should also ensure that the way in which you specify your Python environment (e.g. conda `environment.yml`, `setup.py`, or PIP `requirements.txt` file) will lead to your dependencies being properly installed to support
the GPU hardware specific to the cluster you're running on.

For example, if one of your dependencies is [PyTorch](https://pytorch.org/), you're probably best off writing a conda `environment.yml` file since conda is the preferred way to install PyTorch.
You'll generally want to use the latest supported CUDA version, so in this case your `environment.yml` file could look like this:

```yaml
name: torch-env
channels:
- pytorch
dependencies:
- python=3.9
- cudatoolkit=11.3
- numpy
- pytorch
- ...
```

### Can I use both conda environment and PIP requirements files?

Yes you can. Gantry will initialize your environment using your conda environment file (if you have one)
and then will also check for a PIP requirements file.


### How do I use a CUDA-enabled version of PyTorch on Beaker when I'm using a CPU-only version locally?

One way to handle this would be to start with a `requirements.txt` that lists the `torch` version you need along with any other dependencies, e.g.

```
# requirements.txt
torch==1.11.0
...
```

Then add a conda `environment.yml` somewhere in your repository that specifies exactly how to install PyTorch (and a CUDA toolkit) on Beaker, e.g.:

```yaml
# beaker/environment.yml
name: torch-env
channels:
- pytorch
dependencies:
- python=3.9
- cudatoolkit=11.3
- pytorch==1.11.0  # make sure this matches the version in requirements.txt
```

When you call `gantry run`, use the `--conda` flag to specify the path to your conda env file (e.g. `--conda beaker/environment.yml`).
Gantry will use that env file to initialize the environment, and then will install the rest of your dependencies from the `requirements.txt` file.

### How can I save results or metrics from an experiment?

By default Gantry uses the `/results` directory on the image as the location of the results dataset.
That means that everything your experiment writes to this directory will be persisted as a Beaker dataset when the experiment finalizes.
And you can also create Beaker metrics for your experiment by writing a JSON file called `metrics.json` in the `/results` directory.

### Can I access data on NFS?

Yes. When you choose an on-premise cluster managed by the Beaker team that supports the NFS drive it will be automatically attached to the experiment's container.

### How can I just see the Beaker experiment spec that Gantry uses?

You can use the `--dry-run` option with `gantry run` to see what Gantry will submit without actually submitting an experiment.
You can also use `--save-spec PATH` in combination with `--dry-run` to save the actual experiment spec to a YAML file.

### How can I update Gantry's GitHub token?

Just use the command `gantry config set-gh-token`.

### How can I attach Beaker datasets to an experiment?

Just use the `--dataset` option for `gantry run`. For example:

```bash
gantry run --dataset 'petew/squad-train:/input-data' -- ls /input-data
```

### Why "Gantry"?

A gantry is a structure that's used, among other things, to lift containers off of ships. Analogously Beaker Gantry's purpose is to lift Docker containers (or at least the *management* of Docker containers) away from users.
