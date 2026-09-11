from pathlib import Path
from setuptools import setup, find_packages

this_dir = Path(__file__).parent
long_description = (this_dir / "README.md").read_text(encoding="utf-8")

setup(
    name="baalebos-ai",
    version="1.1.0",
    description="Zero-cost, multi-provider AI gateway CLI and Python SDK",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Baalebos Cloud",
    url="https://github.com/baalebos-cloud/nexus-ai-gateway",
    project_urls={
        "Source": "https://github.com/baalebos-cloud/nexus-ai-gateway",
        "Issues": "https://github.com/baalebos-cloud/nexus-ai-gateway/issues",
        "Documentation": "https://github.com/baalebos-cloud/nexus-ai-gateway#readme",
    },
    license="MIT",
    packages=find_packages(),
    install_requires=["requests"],
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    entry_points={
        "console_scripts": [
            "ai = baalebos_ai.cli:main",
        ],
    },
)
