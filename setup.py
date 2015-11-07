from setuptools import setup

setup(name='doitim',
    version='0.1',
    description='Linux light doit.im client',
    url='http://github.com/valievkarim/doitim',
    author='Karim Valiev',
    author_email='valievkarim@gmail.com',
    license='GPL',
    packages=['doitim'],
    install_requires=['pycurl'],
    scripts=['bin/doitim'],
    zip_safe=False)
