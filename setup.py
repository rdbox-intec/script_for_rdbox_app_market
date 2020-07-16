from setuptools import setup, find_packages

setup(
    name="rdbox_app_market",
    version='1.0',
    description='This app helps you to easily implement useful applications for robot development.',
    author='Tatsuya Fukuta',
    author_email='info-rdbox@intec.co.jp',
    url='https://github.com/rdbox-intec',
    packages=find_packages(),
    entry_points="""
    [console_scripts]
    rdbox_app_market = rdbox_app_market.__main__:launch
    """,
    install_requires=open('requirements.txt').read().splitlines(),
)
