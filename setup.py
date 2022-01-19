import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="dbackup", # Replace with your own username
    version="0.5.1",
    author="David Degerfeldt",
    author_email="david@degerfeldt.se",
    description="My backup solution",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/drdeg/dbackup",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GPLv3",
        "Operating System :: Linux",
    ],
    python_requires='>=3.6',
    install_requires=['fasteners', 'paho-mqtt', 'dpytool']
)