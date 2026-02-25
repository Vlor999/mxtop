from setuptools import setup, find_packages

long_description = 'Performance monitoring CLI tool for Apple Silicon'

setup(
    name='mxtop',
    version='0.1.1',
    author='Timothy Liu',
    author_email='tlkh.xms@gmail.com',
    url='https://github.com/Vlor999/mxtop.git',
    description='Performance monitoring CLI tool for Apple Silicon',
    long_description=long_description,
    long_description_content_type="text/markdown",
    license='MIT',
    packages=find_packages(),
    entry_points={
            'console_scripts': [
                'mxtop = mxtop.mxtop:main'
            ]
    },
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS",
    ),
    keywords='mxtop',
    install_requires=[
        "dashing",
        "loguru",
        "psutil",
    ],
    zip_safe=False
)
