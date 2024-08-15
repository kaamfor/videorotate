from setuptools import setup, find_packages

# pyinstaller --onefile --clean --icon=logo.ico main.py
setup(
    name="videorotate",
    version="1.0.0",
    description="Video processing software",
    long_description='',
    long_description_content_type="text/markdown",
    url="",
    author="Gergo Toth",
    author_email="tgergo@pm.me",
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
    ],
    packages=find_packages(exclude=("tests",)),
    include_package_data=True,
    install_requires=[
        "opencv", "wxpython", "typing"
    ],
    #entry_points={"console_scripts": ["realpython=reader.__main__:main"]},
    python_requires=">=3.6",
)
