import requests


def main():
    response = requests.get(
        "https://pypi.org/simple/beaker-gantry",
        headers={"Accept": "application/vnd.pypi.simple.v1+json"},
        timeout=5,
    )

    if not response.ok:
        raise RuntimeError(
            f"Failed to query latest published version from PyPI (status code {response.status_code}), please try again..."
        )

    latest_version = response.json()["versions"][-1]
    print(f"v{latest_version}")


if __name__ == "__main__":
    main()
