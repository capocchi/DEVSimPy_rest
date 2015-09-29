
from bottle import default_app, run, route, debug, static_file, response, request

import os, sys
import subprocess
import daemon

#import yaml, json
#import StringIO

import __builtin__

__builtin__.__dict__['DEVS_DIR_PATH_DICT'] = {}

sys.path.append(os.path.join('DEVSimPy-2.9'))
sys.path.append(os.path.join('DEVSimPy-2.9', 'DEVSKernel'))

current_path = os.getcwd()
version_dir = 'git'
devsimpy_version_dir = 'version-2.9'

#import DomainInterface.BaseDEVS, DomainBehavior, DomainStructure

# the decorator
def enable_cors(fn):
    def _enable_cors(*args, **kwargs):
        # set CORS headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'

        if request.method != 'OPTIONS':
            # actual request; reply with the actual response
            return fn(*args, **kwargs)

    return _enable_cors

@route('/img/<filepath:path>')
def server_img(filepath):
    return static_file(filepath, root=os.path.join(current_path,'static','img'))

@route('/dsp/<filepath:path>')
def server_dsp(filepath):
    return static_file(filepath, root=os.path.join(current_path,'static','dsp'))

@route('/')
@enable_cors
def serve_homepage():
    return static_file('index.html', root=os.path.join(current_path,'static'))

############################################################################
#
#       Functions
#
############################################################################

### get files with ext extention from path_dir
### TODO : get function from utils.py file in DEVSimPy because its recurcive
def getFiles(path_dir, ext):
    return dict([(entry, open(os.path.join(path_dir, entry), 'r').read() if ext == '.yaml' else {}) \
                for entry in os.listdir(path_dir) \
                if entry.endswith(ext)])

def group(lst, n):
    """group([0,3,4,10,2,3], 2) => [(0,3), (4,10), (2,3)]

    Group a list into consecutive n-tuples. Incomplete tuples are
    discarded e.g.

    >>> group(range(10), 3)
    [(0, 1, 2), (3, 4, 5), (6, 7, 8)]
    """
    return zip(*[lst[i::n] for i in range(n)])

### return the json for JOIN
def getJointJs(d):
    ### get param coming from url
    name = request.params.name

    ### list of ConnectinShape, CodeBlock, ContainerBlock
    docs = []
    l = d[name].split('\r\n')
    #return str(l)
    for i,raw_doc in enumerate(l):
        if raw_doc and ("!!python/object:" in raw_doc or 'label: !!python/unicode' in raw_doc):
            docs.append(raw_doc)

    #return str(docs)

    ### return list of tuples of connected models
    return str(group(map(lambda b: b.split(' ')[-1], filter(lambda a: 'label' in a, docs)),2))

### return a dictionnary
def getJSON(d):

    ### get param coming from url
    name = request.params.name

    if 'all' in request.params:
        return { "success": True, "content": d}
    elif 'name' in request.params:
        if name in d.keys():
            return {"success":True, name:d[name]}
        else:
            return {"success":False, name:"does not exist!"}
    else:
        return { "success": False, "content": []}

### get json dsp files
### /dsp?all to have all dsp json file
### ?name=test.dsp to have test.dsp json file
@route('/dsp', method=['OPTIONS', 'GET'])
@enable_cors
def recipes_dsp():
    d = getFiles(os.path.join(current_path,'static','dsp'), '.dsp')
    return getJSON(d)

@route('/yaml', method=['OPTIONS', 'GET'])
@enable_cors
def recipes_yaml():
    d = getFiles(os.path.join(current_path,'static','yaml'), '.yaml')
    return getJSON(d)

@route('/json', method=['OPTIONS', 'GET'])
@enable_cors
def recipes_json():
    ### get param coming from url
    name_param = request.params.name

    ### if no time limit and .dsp or .yaml file, we can simulate
    if name_param.endswith(('.dsp', '.yaml')):
        dsp_file = os.path.join(current_path,'static', 'dsp' if name_param.endswith('.dsp') else 'yaml', name_param)
        #python_file = os.path.join('DEVSimPy-2.9', 'devsimpy-nogui.py ')
        python_file = os.path.join(current_path, version_dir, 'DEVSimPy', devsimpy_version_dir, 'devsimpy-nogui.py ')

        ### command to be execut
        cmd = "python2.7 "+python_file+dsp_file+" -json"

        ### simulation completed (output is json format)
        output = subprocess.check_output(cmd, shell=True)

    else:
        ### generation failed
        output = {'success':False, 'info': "file does not exist!"}

    return output

### simulate the dsp file
### /simulate?name=test.dsp&time=10
@route('/simulate', method=['OPTIONS', 'GET'])
@enable_cors
def simulate():

    ### get param coming from url
    name_param = request.params.name
    time_param = request.params.time

    ### if no time limit and .dsp or .yaml file, we can simulate
    if name_param.endswith(('.dsp', '.yaml')):

        if time_param in ('ntl', 'inf'):
            time_param = "10000000"

        if time_param.isdigit():
            ### TODO name_param.split('/') if name is relative
            dsp_file = os.path.join(current_path, 'static', 'dsp' if name_param.endswith('.dsp') else 'yaml', name_param)
            #python_file = os.path.join('DEVSimPy-2.9', 'devsimpy-nogui.py ')
            python_file = os.path.join(current_path, version_dir, 'DEVSimPy', devsimpy_version_dir, 'devsimpy-nogui.py ')

            ### command to be execut
            cmd = "python2.7 "+python_file+dsp_file+" "+time_param

            ### simulation completed (output is json format)
            output = subprocess.check_output(cmd, shell=True)

        else:
            ### simulation failed
            output = {'success':False, 'info': "time must be digit!"}
    else:
        ### simulation failed
        output = {'success':False, 'info': "file does not exist!"}

    return output

@route('/results', method=['OPTIONS', 'GET'])
@enable_cors
def results():
    #return "test"
    return request.params.data

debug(True)
#application = default_app()
#with daemon.DaemonContext():
#    run(host='193.48.28.112', port=8080, server='paste')

app = default_app()
from paste import httpserver
httpserver.serve(app, host='193.48.28.112', port=8080)
