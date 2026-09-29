from pathlib import Path

from setuptools import find_packages, setup


README = Path(__file__).with_name("README.md")

if __name__ == "__main__":
    setup(
        name="wiim",
        version="0.2.0",
        author="Linkplay",
        author_email="tao.jiang@linkplay.com",
        description="A Python-based API interface for controlling and communicating with WiiM audio devices.",
        long_description=README.read_text(encoding="utf-8"),
        long_description_content_type="text/markdown",
        url="https://github.com/Linkplay2020/wiim",
        license="MIT",
        package_dir={"": "src"},
        packages=find_packages(where="src"),
        package_data={"wiim": ["py.typed"]},
        include_package_data=True,
        install_requires=[
            "aiohttp",
            "async-upnp-client",
            "zeroconf",
        ],
        classifiers=[
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
        ],
    )
