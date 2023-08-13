from setuptools import setup, find_packages

setup(
    name='setup-data',
    version='0.0.1',
    description='',
    packages=find_packages(exclude=('tests')),
    test_suite="tests"
)