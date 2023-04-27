from setuptools import find_packages, setup

setup(
    name="pyroll",
    version="0.0.10",
    package_dir={"pyroll": "src/pyroll"},
    packages=find_packages(where="pyroll"),
    url="https://github.com/loua19/pyroll",
    author="loua19",
    author_email="loua19@outlook.com",
    license="MIT",
    install_requires=["mido", "progress"],
    extras_require={
        "dev": ["flake8", "black"],
    },
    python_requires=">=3.10",
)
