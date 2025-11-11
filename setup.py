from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="absurd",
    version="0.0.6",
    author="Farshid Ashouri",
    author_email="farshid.ashouri@example.com",
    description="A Python client for the Absurd SQL-based durable execution workflow system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rodmena-limited/python-absurd-client",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",  # Updated to match your LICENSE file
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=[
        "psycopg>=3.0",
    ],
    keywords="workflow, durable-execution, postgresql, database",
)
