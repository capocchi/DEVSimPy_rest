# What is DEVSimPy-rest
DEVSimPy-rest is a Restful API web services for DEVSimPy.
It allow to invoke DEVS simulation service through a rest full request. 
It is based on a no GUI version of the DEVSimPy simulation kernel (DEVSimPy-nogui) which is a part of the DEVSimPy project. 

#Tech
DEVSimPy-rest server uses a number of open source projects to work properly:
* [Bottle](http://bottlepy.org/docs/dev/index.html) - a fast, simple and lightweight WSGI micro web-framework for Python.
* [Python](http://python.org)

#Installation
DEVSimPy-rest is a server solution which needs to be start by invoking the rest_server.py script.
```sh
$ python rest_server.py
```
All parameters used by the server are stored in a param.py file and they need to be filled:
- url_server : url of the host
- port_server : port of the host
