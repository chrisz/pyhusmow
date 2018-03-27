from setuptools import setup

setup(
    name='pyhusmow',
    description='Control your Husqvarna automower using Automower connect API.',
    url='https://github.com/chrisz/pyhusmow',
    author='Christophe Carre',
    license='GPLv3',
    version='0.2.0',
    packages=['pyhusmow'],
    entry_points={
        'console_scripts': [
            'husmow=pyhusmow:main',
            'husmow_logger=pyhusmow.status_logger:main'
        ],
    },
    install_requires=[
        'requests',
        'python-dateutil'
    ],
    zip_safe=False,
)
