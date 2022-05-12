from setuptools import setup

setup(
    name="gira",
    version="0.1",
    py_modules=["gira"],
    install_requires=["Click", "gitpython", "python-slugify"],
    entry_points="""
        [console_scripts]
        gira=gira:gira
    """,
)
