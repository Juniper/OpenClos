#!/usr/bin/env python

from setuptools import setup
import os
import sys

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

exec(read('swagger_render/__version__.py'))


setup(
    name="swagger-render",
    description="Renders Swagger APIs",
    long_description=read("README.rst"),
    version=__version__,
    author="Juhani Imberg",
    author_email="juhani@imberg.com",
    packages=["swagger_render"],
    entry_points={
        "console_scripts": [
            "swagger-render = swagger_render.__main__:main"
        ]
    },
    package_data={
        "swagger_render": ["templates/*.html"]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Topic :: Documentation"
    ],
    install_requires=[
        "jinja2",
        "click",
        "pyyaml",
        "markdown"
    ]
)
