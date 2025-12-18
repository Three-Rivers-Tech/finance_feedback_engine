"""Setup configuration for Finance Feedback Engine."""

from pathlib import Path

from setuptools import find_packages, setup

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10 fallback (tomli optional)
    tomllib = None


def load_metadata():
    """Load project metadata from pyproject.toml to avoid duplicating dependency lists."""

    pyproject_path = Path(__file__).parent / "pyproject.toml"
    if tomllib and pyproject_path.exists():
        data = tomllib.loads(pyproject_path.read_text())
        project = data.get("project", {})
        dependencies = project.get("dependencies", [])
        optional = project.get("optional-dependencies", {})
        return dependencies, optional
    return [], {}


readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

install_requires, extras_require = load_metadata()

setup(
    name="finance-feedback-engine",
    version="2.0.0",
    description="AI-powered finance tool for automated portfolio simulation and trading decisions",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Three Rivers Tech",
    license="Apache License 2.0",
    packages=find_packages(),
    install_requires=install_requires,
    extras_require=extras_require,
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "ffe=finance_feedback_engine.cli.main:cli",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial :: Investment",
    ],
    keywords="finance trading ai automation portfolio cryptocurrency forex",
)
