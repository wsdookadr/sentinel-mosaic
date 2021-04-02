import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sentinel-mosaic",
    version="0.2.0",
    author="Stefan Corneliu Petrea",
    author_email="stefan.petrea@gmail.com",
    description="Tool for joining, clipping and creating mosaics from satellite images of Earth taken by Sentinel-2A and Sentinel-2B, given an initial area of interest",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://wsdookadr.github.io/",
    packages=setuptools.find_packages(),
    scripts=["sentinel-toolbelt.py"],
    install_requires=[
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='==3.8.5',
)
