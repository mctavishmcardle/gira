from setuptools import find_packages, setup

setup(
    name="gira",
    version="0.1",
    packages=find_packages(),
    install_requires=["Click", "gitpython", "python-slugify"],
    entry_points="""
        [console_scripts]
        gira=cli:cli
    """,
)
