from bottle import default_app, route, debug, static_file, response, request

import os
import subprocess
import time
import json
import signal
from datetime import datetime

import __builtin__

#import BaseDEVS, DomainBehavior, DomainStructure

__builtin__.__dict__['DEVS_DIR_PATH_DICT'] = {}

from param import *

### dict of simulation proc
running_sim = {}

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

############################################################################
#
#       Functions
#
############################################################################

def getYAMLFile(name):
    """ Get yaml file with json format
    """

    ### list of yaml filename in yaml_path_dir directory
    filenames = [entry for entry in os.listdir(yaml_path_dir)]

    return dict([(name, open(os.path.join(yaml_path_dir, name), 'r').read())])\
    if name in filenames else {}

def getYAMLFiles():
    """ Get all yamls files in yaml_path_dir
    """

    return dict([(entry, open(os.path.join(yaml_path_dir, entry), 'r').read())\
                for entry in os.listdir(yaml_path_dir)\
                if entry.endswith('.yaml')])

def getYAMLFilenames():
    """ Get all yamls file names in yaml_path_dir
    """

    return dict([(entry, {'last modified':str(time.ctime(os.path.getmtime(os.path.join(yaml_path_dir, entry)))), 'size':str(os.path.getsize(os.path.join(yaml_path_dir, entry))*0.001)+' ko'})\
                for entry in os.listdir(yaml_path_dir)\
                if entry.endswith('.yaml')])

def group(lst, n):
    """group([0,3,4,10,2,3], 2) => [(0,3), (4,10), (2,3)]

    Group a list into consecutive n-tuples. Incomplete tuples are
    discarded e.g.

    >>> group(range(10), 3)
    [(0, 1, 2), (3, 4, 5), (6, 7, 8)]
    """
    return zip(*[lst[i::n] for i in range(n)])

def getJointJs(d):
    """ return the json for JOIN
    """
    ### get param coming from url
    name = request.params.name

    ### list of ConnectinShape, CodeBlock, ContainerBlock
    docs = []
    l = d[name].split('\r\n')

    for i,raw_doc in enumerate(l):
        if raw_doc and ("!!python/object:" in raw_doc or 'label: !!python/unicode' in raw_doc):
            docs.append(raw_doc)

    ### return list of tuples of connected models
    return str(group(map(lambda b: b.split(' ')[-1], filter(lambda a: 'label' in a, docs)),2))

############################################################################
#
#       Routes
#
############################################################################
@route('/img/<filepath:path>')
def server_img(filepath):
    return static_file(filepath, root=os.path.join(current_path,'static','img'))

############################################################################
@route('/dsp/<filepath:path>')
def server_dsp(filepath):
    return static_file(filepath, root=os.path.join(current_path,'static','dsp'))

############################################################################
@route('/')
@enable_cors
def serve_homepage():
    return static_file('index.html', root=os.path.join(current_path, 'static'))

############################################################################
@route('/info', method=['OPTIONS', 'GET'])
@enable_cors
def recipes_info():
    """ Get server info
    """
    from platform import python_version

    data = {'devsimpy-version':os.path.basename(os.path.dirname(devsimpy_nogui)),
            'devsimpy-libraries': filter(lambda a: a not in [".directory", "Basic", "__init__.py"], os.listdir(os.path.join(os.path.dirname(devsimpy_nogui), 'Domain'))),
            'python-version': python_version(),
            ### TODO read __init__.py to build plugins list
            'devsimpy-plugins':filter(lambda a: a not in ["__init__.py"], os.listdir(os.path.join(os.path.dirname(devsimpy_nogui), 'plugins'))),
            'url-server':url_server,
            'machine-server': subprocess.check_output("uname -m", shell=True),
            'os-server': subprocess.check_output("uname -o", shell=True),
            'machine-version-server': subprocess.check_output("uname -v", shell=True)
            }

    return data

############################################################################
@route('/yaml', method=['OPTIONS', 'GET'])
@enable_cors
def recipes_yaml():
    """ Get yaml description
    """
    if 'all' in request.params:
        data = getYAMLFiles()
    elif 'name' in request.params:
        data = getYAMLFile(request.params.name)
    elif 'filenames' in request.params:
        data = getYAMLFilenames()
    else:
        data = {}

    return { "success": data!={} and data!=[], "content": data }

############################################################################
### POST body example :
### {"filename":"test.yaml",
###  "model":"RandomGenerator_0",
###  "args":{"maxStep":"1",
###          "maxValue":"100",
###          "minStep":"1",
###          "minValue":"0",
###          "start":"0"}}
@route('/yaml/save', method=['OPTIONS', 'POST'])
@enable_cors
def save_yaml():
    """ Update yaml file from devsimpy-mob
    """
    # read POST data as JSON
    data = request.json
    # update filename to absolute path
    data['filename'] = os.path.join(yaml_path_dir, data['filename'])
    # Get the expected input string from JSON model and args data
    dataS1 = json.dumps(data)
    dataS2 = str(dataS1.replace("\"","'"))

    # perform update (blocking operation)
    cmd = ["python2.7", devsimpy_nogui, "-update", dataS2]
    output = subprocess.check_output(cmd) #empty

    return {'success':True, 'output':output}

############################################################################
### xxx.pythonanywhere.com/yaml/labels?name=test1.yaml
@route('/yaml/labels', method=['OPTIONS', 'GET'])
@enable_cors
def labels_yaml():
    """ get the model blocks list from yaml
    """
    # get the models names (blocking operation)
    cmd = ["python2.7", devsimpy_nogui, "-models", os.path.join(yaml_path_dir, request.params.name)]
    output = subprocess.check_output(cmd) # output is JSON, rstrip('\r\n') makes it easier to read by human

    return {'success':True, 'output':eval(output.rstrip('\r\n'))}


############################################################################
### xxx.pythonanywhere.com/json?name=test1.yaml
@route('/json', method=['OPTIONS', 'GET'])
@enable_cors
def recipes_json():
    """
    """
    ### get param coming from url
    name_param = request.params.name

    ### if no time limit and .dsp or .yaml file, we can simulate
    if name_param.endswith(('.dsp', '.yaml')):
        dsp_file = os.path.join(dsp_path_dir if name_param.endswith('.dsp') else yaml_path_dir, name_param)

        ### command to be executed
        cmd = ["python2.7", devsimpy_nogui, dsp_file,"-json"]

        ### transformation completed (output is json format)
        output = subprocess.check_output(cmd)

    else:
        ### generation failed
        output = {'success':False, 'info': "file does not exist!"}

    return output

############################################################################
### simulate the model identified by its dsp or yaml file
### /simulate?name=test.dsp&time=10
### or /simulate?name=test.yaml&time=10
@route('/simulate', method=['OPTIONS', 'GET'])
@enable_cors
def simulate():
    """
    """
    ### Check that the given model name is valid
    model_filename     = request.params.name
    path               = dsp_path_dir if model_filename.endswith('.dsp') else yaml_path_dir
    abs_model_filename = os.path.join(path, model_filename)
    if not os.path.exists(abs_model_filename):
        return {'success':False, 'info': "file does not exist! "+ abs_model_filename}

    ### Check that the given simulation duration is valid
    sim_duration = request.params.time
    if sim_duration in ('ntl', 'inf'):
        sim_duration = "10000000"
    if not sim_duration.isdigit():
        return {'success':False, 'info': "time must be digit!"}

    ### Delete old result files .dat
    for name in filter(lambda fn: fn.endswith('.dat') and fn.split('_')[0] == os.path.splitext(model_filename)[0], os.listdir(path)):
        os.remove(os.path.join(path, name))

    ### Launch simulation
    ### NB : Don't set shell=True because then it is not possible to interact with the process inside the shell
    cmd = ['python2.7', devsimpy_nogui, abs_model_filename, str(sim_duration)]
    fout = open('simuout.dat', 'w+') # where simulation execution report will be written
    fin  = open('user.in', 'w') # where interaction with user will be written
    process = subprocess.Popen(cmd, stdout=fout, stderr=subprocess.STDOUT, close_fds=True)
    # Call to Popen is non-blocking, BUT, the child process inherits the file descriptors from the parent,
    # and that will include the web app connection to the WSGI server,
    # so the process needs to run and finish before the connection is released and the server notices that the request is finished.
    # This is solved by passing close_fds=True to Popen
    running_sim[model_filename] = {'process':process, 'output_name':'simuout.dat', 'input_name':'user.in'}

    return {'success':True}

############################################################################
### /modify
### example POST body : {"simulation_name":"testInteraction.yaml","OPort":"0","param_name":"outvalue","param_value":"12"}
@route('/modify', method=['POST'])
@enable_cors
def modify():
    data = request.json
    simu_name = data['simulation_name']
    if (running_sim.has_key(simu_name)): #TODO test if simulation is in progress
        fin = open(running_sim[simu_name]['input_name'], 'a')
        del data['simulation_name']
        data['date'] = datetime.strftime(datetime.today(), "%Y-%m-%d %H:%M:%S")
        fin.write(json.dumps(data)+'\n')
        fin.close()
        return {'success':True}
    else:
        return {'success':False, 'info':"no simulation in progress is named " + simu_name}

############################################################################
### /result?name=test.yaml # TODO rename to status
@route('/result', method=['OPTIONS', 'GET'])
@enable_cors
def result():
    simu_name = request.params.name

    if not running_sim.has_key(simu_name):
        return {'success':False, 'info':"no simulation is named " + simu_name}
    else:
        running_sim[simu_name]['process'].poll()
        if (running_sim[simu_name]['process'].returncode == None):
            return {'success':True, 'info':"simulation " + simu_name + " is running"}
        else:
            fout=open(running_sim[simu_name]['output_name'], 'r')
            output = ""
            for line in fout:
                output = output + line
            fout.close()
            #TODO del dict_proc_sim when ...?
            return output#{'success':True, 'report':output}

############################################################################
### /pause?name=test.yaml
@route('/pause', method=['OPTIONS', 'GET'])
@enable_cors
def pause():
    """
    """
    simu_name = request.params.name
    if not running_sim.has_key(simu_name):
        return {'success':False, 'info':"no simulation is named " + simu_name}
    if (running_sim[simu_name]['process'].returncode != None):
        return {'success':False, 'info':"simulation " + simu_name + "is terminated"}
    else:
        running_sim[simu_name]['process'].send_signal(signal.SIGSTOP)
        return {'success':True, 'info':"simulation " + simu_name + "is paused"}


############################################################################
### /pause?name=test.yaml
@route('/resume', method=['OPTIONS', 'GET'])
@enable_cors
def resume():
    """
    """
    simu_name = request.params.name
    if not running_sim.has_key(simu_name):
        return {'success':False, 'info':"no simulation is named " + simu_name}
    if (running_sim[simu_name]['process'].returncode != None):
        return {'success':False, 'info':"simulation " + simu_name + "is terminated"}
    else:
        running_sim[simu_name]['process'].send_signal(signal.SIGCONT)
        return {'success':True, 'info':"simulation " + simu_name + "is resumed"}

############################################################################
### /pause?name=test.yaml
@route('/kill', method=['OPTIONS', 'GET'])
@enable_cors
def kill():
    """
    """
    simu_name = request.params.name
    if not running_sim.has_key(simu_name):
        return {'success':False, 'info':"no simulation is named " + simu_name}
    if (running_sim[simu_name]['process'].returncode != None):
        return {'success':True, 'info':"simulation " + simu_name + "is terminated"}
    else:
        running_sim[simu_name]['process'].send_signal(signal.SIGKILL)
        return {'success':True, 'info':"simulation " + simu_name + "is killed"}

############################################################################
### /pause?name=result.dat
@route('/plot', method=['OPTIONS', 'GET'])
@enable_cors
def plot():
    """
    """
    filename = request.params.name

    # Build the diagram data as :
    # - 1 list of labels (X or Time axis) called category TBC : what if time delta are not constant???
    # - 1 list of values (Y or Amplitude axis) called data
    data = []
    category = []
    with open(os.path.join(yaml_path_dir, filename)) as fp:
        for line in fp:
            a,b = line.split(" ")
            category.append({'label':a})
            data.append({'value':b.rstrip('\r\n')})

    result = {
                "chart": {
                    "caption": filename,
                    "subCaption": "",
                    "xAxisName": "Time",
                    "yAxisName": "Amplitude",
                    "showValues": "0",
                    "numberPrefix": "",
                    "showBorder": "0",
                    "showShadow": "0",
                    "bgColor": "#ffffff",
                    "paletteColors": "#008ee4",
                    "showCanvasBorder": "0",
                    "showAxisLines": "0",
                    "showAlternateHGridColor": "0",
                    "divlineAlpha": "100",
                    "divlineThickness": "1",
                    "divLineIsDashed": "1",
                    "divLineDashLen": "1",
                    "divLineGapLen": "1",
                    "lineThickness": "3",
                    "flatScrollBars": "1",
                    "scrollheight": "10",
                    "numVisiblePlot": "10",
                    "showHoverEffect": "1"
                }}
    result.update({"categories": [{'category':category}], 'dataset': [{'data':data}]})

    return result


############################################################################
#
#     Application definition
#
############################################################################
debug(True)
application = default_app()

if __name__ == "__main__":
    from paste import httpserver
    httpserver.serve(application, host=url_server, port=port_server)