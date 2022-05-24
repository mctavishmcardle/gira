from setuptools import find_packages, setup

setup(
    name="gira",
    version="1.0.0",
    packages=find_packages(),
    install_requires=["Click", "gitpython", "python-slugify", "marko", "tabulate"],
    entry_points="""
        [console_scripts]
        gira=cli:cli
    """,
)
