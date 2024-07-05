from setuptools import setup, find_packages

setup(
    name='ControlConstants',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        "numpy"
    ],
    author='https://github.com/roosleek',
    description='A mini-library for communicating with ControlConstants using python3.',
    url='https://github.com/roosleek/ControlConstants',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)