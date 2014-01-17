#!/usr/bin/env python

from setuptools import setup
import os

from op import __version__

cwd = os.path.dirname(os.path.abspath(__file__))

long_description = ''
with open(os.path.join(cwd, 'README.rst')) as fp:
    long_description = fp.read()

setup(
    name='op',
    version=__version__,
    license='BSD',
    description='Private pastebin (client-side implementation)',
    long_description=long_description,
    author='Rafael G. Martins',
    author_email='rafael@rafaelmartins.eng.br',
    url='http://op.rtfd.org/',
    py_modules=['op'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'httplib2 >= 0.7.4',
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Programming Language :: Python :: 2.7',
    ],
    entry_points={'console_scripts': ['op = op:main']},
)
