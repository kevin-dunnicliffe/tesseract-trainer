import re
import os
from setuptools import setup

VERSION = re.search("__version__ = '([^']+)'", open(
    os.path.join(os.path.dirname(__file__), 'tesseract_trainer', '__init__.py')
).read().strip()).group(1)

setup(
    name="tesseract-trainer",
    version=VERSION,
    license=open('LICENSE.txt').read(),
    description='A small framework taking over the manual tesseract training process described in the Tesseract Wiki',
    author="Kevin Dunnicliffe",
    author_email='kevin@kdassoc.com',
    packages=['tesseract_trainer'],
    install_requires=['Pillow>=1.1.7'],
    keywords=['tesseract', 'OCR', 'optical character recogniton', 'training'],
    scripts=['tesseract_trainer/tesstrain','train'],
    classifiers=[
           'Development Status :: 3 - Alpha',
           'Environment :: Console',
           'Intended Audience :: Developers',
           'License :: OSI Approved :: BSD License',
           'Natural Language :: English',
           'Operating System :: POSIX :: Linux',
           'Operating System :: Unix',
           'Operating System :: MacOS :: MacOS X',
           'Programming Language :: Python :: 2.7',
           'Programming Language :: Python :: 3.5',
           'Topic :: Scientific/Engineering :: Artificial Intelligence',
           'Topic :: Scientific/Engineering :: Image Recognition',
        ],
    long_description=open('README.md').read(),  # Long description: content of README.md (DRY),
)
