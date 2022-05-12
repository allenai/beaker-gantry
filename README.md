<div align="center">
<!-- TODO: Add logo -->
<!-- <br> -->
<!-- <img src="https://raw.githubusercontent.com/allenai/beaker-py/main/docs/source/_static/beaker-500px-transparent.png" width="200"/> -->
<!-- <br> -->
<!-- <br> -->
<h1>Beaker Gantry</h1>
<p>Gantry streamlines running Python experiments in <a href="https://beaker.org">Beaker</a> by managing containers and boilerplate for you</p>
<hr/>
<!-- TODO: Add badges once this is open source -->
<!-- <a href="https://github.com/allenai/beaker-gantry/actions"> -->
<!--     <img alt="CI" src="https://github.com/allenai/beaker-gantry/workflows/Main/badge.svg?event=push&branch=main"> -->
<!-- </a> -->
<!-- <a href="https://pypi.org/project/beaker-gantry/"> -->
<!--     <img alt="PyPI" src="https://img.shields.io/pypi/v/beaker-gantry"> -->
<!-- </a> -->
<!-- <a href="https://github.com/allenai/beaker-gantry/blob/main/LICENSE"> -->
<!--     <img alt="License" src="https://img.shields.io/github/license/allenai/beaker-gantry.svg?color=blue&cachedrop"> -->
<!-- </a> -->
<!-- <br/> -->
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

- Pure Python.
- Minimal dependencies.

### Who is this for?

**gantry** is for both new and seasoned Beaker users who need to run Python batch jobs (as opposed to interactive sessions) from a rapidly changing repository.
Without **gantry**, this workflow usually looks like this:

1. Add a Dockerfile to your repository.
2. Build the Docker image locally.
3. Push the Docker image to Beaker.
4. Write a YAML Beaker experiment spec that points to the image you just uploaded.
5. Submit the experiment spec.
6. Make changes and repeat from step 2.

This requires experience with Docker, experience writing Beaker experiment specs, and a fast and reliable internet connection (a luxury that some of us don't have, especially in the WFH era 🙃).

With **gantry**, on the other hand, that same workflow simplifies down to this:

1. Write a conda `environment.yml` file, or simply a PIP `requirements.txt` and/or `setup.py` file.
2. Commit and push your changes.
3. Submit and track a Beaker experiment with the `gantry run` command.
4. Make changes and repeat from step 2.

## In this README

- 💾 [Installing](#installing)
- 🚀 [Quick start](#quick-start)
- 👓 [Best practices](#best-practices)
- ❓ [FAQ](#faq)

<br>

*For developers* 👇

- [CHANGELOG](https://github.com/allenai/beaker-gantry/blob/main/CHANGELOG.md)
- [CONTRIBUTING](https://github.com/allenai/beaker-gantry/blob/main/CONTRIBUTING.md)

## Installing

### Installing with `pip`

**gantry** is available [on PyPI](https://pypi.org/project/gantry/). Just run

```bash
pip install gantry
```

### Installing from source

To install **gantry** from source, first clone [the repository](https://github.com/allenai/gantry):

```bash
git clone https://github.com/allenai/gantry.git
cd gantry
```

Then run

```bash
pip install -e .
```

## Quick start

### Use conda

Adding a [conda environment file](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#create-env-file-manually) will make your exact Python environment much easier to reproduce.
You don't necessarily need to write the `environment.yml` file manually either.
If you've already initialized a conda environment locally, you can just run:

```bash
conda env export --from-history
```

See [Exporting an Environment File Across Platforms](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#exporting-an-environment-file-across-platforms) for more details.

## Best practices

## FAQ
