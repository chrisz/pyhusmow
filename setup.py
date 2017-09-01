from setuptools import setup

setup(
    name='pyhusmow',
    description='Control your Husqvarna automower using Automower connect API.',
    url='https://github.com/yeah/pyhusmow',
    author='Christophe Carre',
    license='GPLv3',
    version='0.1',
    packages=['pyhusmow'],
    scripts=[
        'bin/husmow',
        'bin/status_logger'
    ],
    install_requires=[
        'requests',
        'python-dateutil'
    ],
    zip_safe=False
)
