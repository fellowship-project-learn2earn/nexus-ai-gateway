from setuptools import setup, find_packages
from pathlib import Path

this_dir = Path(__file__).parent
long_description = (this_dir / "README.md").read_text(encoding="utf-8") if (this_dir / "README.md").exists() else ""

setup(
    name='baalebos-ai',
    version='1.0.0',
    description='Official Python client and terminal CLI for the Baalebos AI Gateway',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Baalebos AI Team',
    url='https://github.com/baalebos-cloud/nexus-ai-gateway',
    project_urls={
        'Source': 'https://github.com/baalebos-cloud/nexus-ai-gateway',
        'Bug Tracker': 'https://github.com/baalebos-cloud/nexus-ai-gateway/issues',
    },
    packages=find_packages(),
    install_requires=['requests', 'httpx'],
    python_requires='>=3.8',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    license='MIT',
    entry_points={
        'console_scripts': [
            'ai = baalebos_ai.cli:main',
        ],
    },
)