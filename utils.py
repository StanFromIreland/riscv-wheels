import datetime as dt
import json
import re
import requests_cache


BASE_URL = "https://pypi.org/pypi"
RISE_REGISTRY_URL = "https://pypi.riseproject.dev/simple"

DEPRECATED_PACKAGES = {
    "BeautifulSoup",
    "bs4",
    "distribute",
    "django-social-auth",
    "nose",
    "pep8",
    "pycrypto",
    "pypular",
    "sklearn",
    "y-py",
}

# Keep responses for one hour
SESSION = requests_cache.CachedSession("requests-cache", expire_after=60 * 60)


def get_json_url(package_name):
    return BASE_URL + "/" + package_name + "/json"


def normalize(package_name: str) -> str:
    """Normalise a package name for a simple index URL.

    https://packaging.python.org/en/latest/specifications/name-normalization/
    """
    return re.sub(r"[-_.]+", "-", package_name).lower()


def in_rise_registry(package_name: str) -> bool:
    """Whether the RISE riscv64 registry has wheels for this package."""
    url = f"{RISE_REGISTRY_URL}/{normalize(package_name)}/"
    try:
        response = SESSION.get(url, allow_redirects=False)
    except Exception as e:
        print(f" ! Could not check the RISE registry for {package_name}: {e}")
        return False

    return response.status_code == 200


def annotate_wheels(packages, to_chart: int) -> list[dict]:
    print("Getting wheel data...")
    num_packages = len(packages)
    total = 0
    keep = []
    for index, package in enumerate(packages):
        print(f"{total + 1}/{to_chart} {index + 1}/{num_packages} {package['name']}")
        if package["name"] in DEPRECATED_PACKAGES:
            continue

        has_other_binary_wheel = False
        has_riscv64_wheel = False
        has_pure_python_wheel = False
        in_registry = False
        url = get_json_url(package["name"])
        response = SESSION.get(url)
        if response.status_code != 200:
            print(" ! Skipping " + package["name"])
            continue

        data = response.json()

        for download in data["urls"]:
            if download["packagetype"] == "bdist_wheel":
                # The wheel filename is:
                # {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl
                # https://packaging.python.org/en/latest/specifications/binary-distribution-format/#file-name-convention
                platform_tag = download["filename"].removesuffix(".whl").split("-")[-1]

                # A wheel may be tagged for several platforms at once, for
                # example manylinux_2_39_riscv64.musllinux_1_2_riscv64
                if "riscv64" in platform_tag:
                    has_riscv64_wheel = True
                elif platform_tag != "any":
                    has_other_binary_wheel = True
                else:
                    has_pure_python_wheel = True

        if has_riscv64_wheel:
            package["css_class"] = "success"
            package["icon"] = "\u2713"  # Check mark
        elif has_other_binary_wheel:
            in_registry = in_rise_registry(package["name"])
            if in_registry:
                package["css_class"] = "rise"
                package["icon"] = "📦"
            elif has_pure_python_wheel:
                package["css_class"] = "pure-py"
                package["icon"] = "🐍"
            else:
                package["css_class"] = "warning"
                package["icon"] = "\u2717"  # Ballot X
        else:
            # Don't show packages with only sdists or pure Python wheels
            continue

        package["riscv64_wheel"] = has_riscv64_wheel
        package["rise_registry"] = in_registry

        keep.append(package)
        total += 1
        if total == to_chart:
            break

    return keep


def get_top_packages():
    print("Getting packages...")

    with open("top-pypi-packages.json") as data_file:
        packages = json.load(data_file)["rows"]

    # Rename keys
    for package in packages:
        package["downloads"] = package.pop("download_count")
        package["name"] = package.pop("project")

    return packages


def save_to_file(packages, file_name):
    now = dt.datetime.now(tz=dt.timezone.utc)
    with open(file_name, "w") as f:
        f.write(
            json.dumps(
                {
                    "data": packages,
                    "last_update": now.strftime("%A, %d %B %Y, %X %Z"),
                },
                indent=1,
            )
        )
