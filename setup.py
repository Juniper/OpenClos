from setuptools import setup, find_packages
from os import path

lines = [line.strip() for line in open('requirements.txt')]
requirements = [line for line in lines if line and not line.startswith(('-', '#'))]

setup(
    name='OpenClos',
    namespace_packages=['jnpr'],

    # Versions should comply with PEP440.  For a discussion on single-sourcing
    # the version across setup.py and the project code, see
    # http://packaging.python.org/en/latest/tutorial.html#version
    version='2.5.dev1',

    description='OpenClos Python project',
    long_description= \
      '''OpenClos is a python automation tool to perform following 
             1. Create scalable Layer-3 IP Fabric using BGP 
             2. Troubleshoot L2 and L3 connectivity 
             3. Reporting different Fabric statistics 
      ''',

    # The project's main homepage.
    url='https://github.com/Juniper/OpenClos', 

    # Author details
    author='Moloy',
    author_email='openclos@juniper.net',

    # Choose your license
    license='Apache 2.0',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   2 - Pre-Alpha
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 2 - Pre-Alpha',

        # Indicate who your project is intended for
        'Intended Audience :: Developers',
        'Intended Audience :: Telecommunications Industry',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Networking',
	'Topic :: System :: Networking :: Monitoring',

        # Pick your license as you wish (should match "license" above)
        'License :: OSI Approved :: Apache Software License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],

    # What does your project relate to?
    keywords='Layer-3 fabric clos leaf spine',

    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(),

    # List run-time dependencies here.  These will be installed by pip when your
    # project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/technical.html#install-requires-vs-requirements-files
    install_requires=requirements,

    # If there are data files included in your packages that need to be
    # installed, specify them here.  If using Python 2.6 or less, then these
    # have to be included in MANIFEST.in as well.
    package_data={
        'jnpr.openclos': ['conf/*.yaml', 'conf/*.json', 'conf/junosTemplates/*', 'conf/cablingPlanTemplates/*', 'conf/ztp/*', 'conf/junosEznc/*', 'data/.dat', 'script/*', 'tests/*.py', 'tests/unit/*.py'],
        '': ['./*.txt'],
    },

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages.
    # see http://docs.python.org/3.4/distutils/setupscript.html#installing-additional-files
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    #data_files=[('my_data', ['data/data_file'])],

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # pip to create the appropriate form of executable for the target platform.
    #entry_points={
    #   'console_scripts': [
    #       'sample=sample:main',
    #   ],
    #},
)
