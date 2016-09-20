# -*- coding: utf-8 -*-


from setuptools import find_packages, setup


def readfile(path):
    with open(path, 'rb') as stream:
        return stream.read().decode('utf-8')


readme = readfile('README.rst')
version = readfile('smartmob_filestore/version.txt').strip()


setup(
    name='smartmob-filestore',
    url='https://github.com/smartmob-project/smartmob-filestore',
    description='Naive asyncio-based HTTP file server',
    long_description=readme,
    keywords='asyncio fileserver',
    license='MIT',
    maintainer='Andre Caron',
    maintainer_email='ac@smartmob.org',
    version=version,
    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS :: MacOS X',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.5',
        'Topic :: Software Development :: Libraries',
    ],
    packages=find_packages(),
    package_data={
        'smartmob_filestore': [
            'version.txt',
        ],
    },
    entry_points={
        'console_scripts': [
            'smartmob-filestore = smartmob_filestore.__main__:entry_point',
         ],
    },
    install_requires=[
        'aiohttp>=1,<2',
        'aiotk>=0.2,<0.3',
        'fluent-logger>=0.4,<0.5',
        'structlog>=16,<17',
    ],
)
