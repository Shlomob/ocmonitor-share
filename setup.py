"""Setup script for OpenCode Monitor."""

from setuptools import setup, find_packages
import os

# Read version from __init__.py
version = {}
with open(os.path.join("ocmonitor", "__init__.py")) as f:
    exec(f.read(), version)

# Read long description from README
long_description = ""
if os.path.exists("README.md"):
    with open("README.md", "r", encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="ocmonitor",
    version=version["__version__"],
    description="Analytics and monitoring tool for OpenCode AI coding sessions",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="OpenCode Monitor Team",
    author_email="",
    url="https://github.com/Shlomob/ocmonitor-share",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "ocmonitor": ["*.toml", "*.json", "tui/*.tcss"],
    },
    install_requires=[
        "click>=8.0.0",
        "rich>=13.0.0",
        "textual>=0.50.0",
        "pydantic>=2.0.0",
        "toml>=0.10.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-click>=1.1.0",
            "pytest-mock>=3.10.0",
            "coverage>=7.0.0",
            "black>=22.0.0",
            "isort>=5.10.0",
            "flake8>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "ocmonitor=ocmonitor.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Tools",
        "Topic :: System :: Monitoring",
    ],
    python_requires=">=3.8",
    keywords="opencode ai coding analytics monitoring tokens cost",
)