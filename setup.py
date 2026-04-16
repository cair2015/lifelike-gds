import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="lifelike_gds",
    version="0.0.1",
    author="Lifelike Team, Ethan Sanchez <https://github.com/esanche06>, Nathan Weinstein <https://github.com/NathanWeinstein>, Dominik Maszczyk <https://github.com/Skitionek>, Alessandro Negro <https://github.com/alenegro81>",
    author_email="lifelike@biosustain.dtu.dk",
    description="A collection of GDS packages used by the Lifelike application",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/SBRG/GDS",
    project_urls={
        "Bug Tracker": "https://github.com/SBRG/GDS/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.9",
    install_requires=[
        "pandas>=2.0",
        "numpy>=1.25",
        "simplejson>=3.17",
        "networkx<3.0",
        "scipy>=1.9",
        "python-arango>=7.6",
        "python-dotenv>=1.0",
        "xlsxwriter>=3.0",
        "neo4j>=5.28.3"
    ],
    extras_require={
        "dev": [
            "black~=21.9b0",
            "pre-commit~=2.15.0",
            "pytest~=6.2.5",
            "build",
            "jupyterlab",
        ],
    },
    package_data={"lifelike_gds": ["**/*.yml"]},
    include_package_data=True,
)
