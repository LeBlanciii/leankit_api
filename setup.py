import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name='leankit',
    version='0.0.5',
    author='John LeBlanc',
    author_email='johnleblanciii@gmail.com',
    description='Leankit Endpoints',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/LeBlanciii/leankit_api',
    project_urls={
    },
    license='MIT',
    packages=['leankit'],
    install_requires=['requests', 'python-dateutil'],
)
