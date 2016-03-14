from bottle import default_app, route, debug, static_file, response, request

import os
import subprocess
import time
import json
import signal
import socket
from datetime import datetime

import __builtin__

#import BaseDEVS, DomainBehavior, DomainStructure

__builtin__.__dict__['DEVS_DIR_PATH_DICT'] = {}

from param import *

### global variables
global_running_sim = {}
global_simu_id = 0

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
    """ Get yaml file
    """
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


def getModelAsJSON(model_filename):
    """ Run a script to translate the DSP or YAML model description to JSON
    """
    if model_filename.endswith(('.dsp', '.yaml')):
        model_abs_filename = os.path.join(dsp_path_dir if model_filename.endswith('.dsp') else yaml_path_dir, model_filename)
        ### execute command as a subprocess
        cmd = ["python2.7", devsimpy_nogui, model_abs_filename, "-json"]
        output = subprocess.check_output(cmd)
    else:
        output = "unexpected filename : " + model_filename

    return output

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
#   HOME
############################################################################

@route('/')
@enable_cors
def serve_homepage():
    return static_file('index.html', root=os.path.join(current_path, 'static'))

############################################################################
#   SERVER INFORMATION
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
#   RESOURCE = MASTER MODEL
############################################################################
#   Models collection
############################################################################

@route('/models', method=['GET'])
@enable_cors
def models_list():
    """ Return the list of the models available on the server
        with filename, date and size
    """
    data = getYAMLFilenames()

    return jsom.loads(data)

#   Model representation
############################################################################

@route('/models/<model_filename>', method=['GET'])
@enable_cors
def model_representation(model_filename):
    """ Return the representation of the model
        according to requested content type
    """
    if request.headers['Accept'] == 'application/json':
        data = getModelAsJSON(model_filename)
    elif request.headers['Accept'] == 'text/x-yaml':
        data = getYAMLFile(model_filename)
    else:
        return {"success":False, "info":"unexpected Accept type = " + request.headers['Accept']}

    return { "success": data!={} and data!=[], "model": data }

############################################################################
#    RESOURCE = ATOMIC MODEL = BLOCK
############################################################################
#   Blocks collection
############################################################################

@route('/models/<model_filename>/blocks', method=['GET'])
@enable_cors
def model_blocks_list(model_filename):
    """ get the model blocks list from yaml
    """
    # get the models names (blocking operation)
    cmd = ["python2.7", devsimpy_nogui, os.path.join(yaml_path_dir, model_filename), "-blockslist"]
    output = subprocess.check_output(cmd)

    return {'success':True, 'blocks':output}#eval(output.rstrip('\r\n'))}# output is JSON, rstrip('\r\n') makes it easier to read by human

#   Block representation (useful part = parameters)
############################################################################

@route('/models/<model_filename>/blocks/<block_label>', method=['GET'])
@enable_cors
def model_block_parameters(model_filename, block_label):
    """ get the parameters of the block
    """
    # get the models names (blocking operation)
    cmd = ["python2.7", devsimpy_nogui, os.path.join(yaml_path_dir, model_filename), "-getblockargs", block_label]
    output = subprocess.check_output(cmd)
    # output is JSON, rstrip('\r\n') makes it easier to read by human

    return {'success':True, 'block':eval(output.rstrip('\r\n'))}

#   Block update
#   body example : {"maxStep":1, "maxValue":100, "minStep":1, "minValue":0, "start":0}
############################################################################

@route('/models/<model_filename>/blocks/<block_label>', method=['PUT'])
@enable_cors
def save_yaml(model_filename, block_label):
    """ Update yaml file from devsimpy-mob
    """
    # update filename to absolute path
    model_abs_filename = os.path.join(yaml_path_dir, model_filename)
    # Get the expected input string from JSON request body
    data = request.json
    dataS1 = json.dumps(data)
    dataS2 = str(dataS1.replace("\"","'"))

    # perform update (blocking operation)
    cmd = ["python2.7", devsimpy_nogui, model_abs_filename, "-setblockargs", block_label, dataS2]
    output = subprocess.check_output(cmd)

    return {'success':True, 'new_block':eval(output.rstrip('\r\n'))}


############################################################################
#    RESOURCE = SIMULATION
############################################################################
#    Useful methods
############################################################################
def update_status (simu_name):
    """
        Test if the simulation exists and
        if it does, tests if it is still alive
        possible statuses : RUNNING / PAUSED / FINISHED / UNKNOWN
    """
    if not global_running_sim.has_key(simu_name):
        return "UNKNOWN " + simu_name

    if 'FINISHED' not in global_running_sim[simu_name]['data']['status']:
        global_running_sim[simu_name]['process'].poll()
        returncode = global_running_sim[simu_name]['process'].returncode
        if (returncode != None):
            global_running_sim[simu_name]['data']['status'] = "FINISHED with exit code " + str(returncode)

    return global_running_sim[simu_name]['data']['status']

def pause_or_resume (simu_name, action):
    """
    """
    current_status = update_status (simu_name)

    if current_status in ("RUNNING", "PAUSED"):
        CONVERT = {
            'PAUSE'  : {'expected_thread_status' : 'PAUSED',  'sim_status': "PAUSED"},
            'RESUME' : {'expected_thread_status' : 'RESUMED', 'sim_status': "RUNNING"}}

        thread_status = send_via_socket(simu_name, action)
        if thread_status == CONVERT[action]['expected_thread_status']:
            global_running_sim[simu_name]['data']['status'] = CONVERT[action]['sim_status']
            return {'success':True, 'status': thread_status}
        else:
            return {'success':False, 'info': thread_status, 'expected':CONVERT[action]['expected_thread_status']}
    else:
        return {'success':False, 'info': current_status}

def send_via_socket(simu_name, data):
    """ send data string to the simulation identified by simu_name
    """
    try:
        socket_address = '\0' + global_running_sim[simu_name]['data']['username'] + '.' + simu_name
        comm_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        #socket_address = ('localhost', 5555)
        #comm_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        comm_socket.connect(socket_address)
        comm_socket.sendall(data)
        status = comm_socket.recv(1024)
        comm_socket.close()
    except:
        status = 'SOCKET ERROR'
        comm_socket.close()

    return status

#    Simulation collection
############################################################################

@route('/simulations', method=['GET'])
@enable_cors
def simulations_list():
    """
    """
    sim_list = {}
    for simu_name in global_running_sim :
        update_status (simu_name)
        sim_list[simu_name] = global_running_sim[simu_name]['data']

    return sim_list

#    Simulation creation
#    body example :  {"model_filename":"test.yaml", "simulated_duration":"50"}
############################################################################

@route('/simulations', method=['POST'])
@enable_cors
def simulate():
    """
    """
    ### Get data from JSON body
    data = request.json
    ### Check that the given model name is valid
    model_filename     = data['model_filename']
    path               = dsp_path_dir if model_filename.endswith('.dsp') else yaml_path_dir
    abs_model_filename = os.path.join(path, model_filename)
    if not os.path.exists(abs_model_filename):
        return {'success':False, 'info': "file does not exist! "+ abs_model_filename}

    ### Check that the given simulation duration is valid
    sim_duration = data['simulated_duration']
    if sim_duration in ('ntl', 'inf'):
        sim_duration = "10000000"
    if not sim_duration.isdigit():
        return {'success':False, 'info': "time must be digit!"}

    ### Delete old result files .dat
    for name in filter(lambda fn: fn.endswith('.dat') and fn.split('_')[0] == os.path.splitext(model_filename)[0], os.listdir(path)):
        os.remove(os.path.join(path, name))

    ### Create simulation name - TODO store in DB
    model_name     = model_filename.split('.')[0]
    global global_simu_id
    global_simu_id += 1
    simu_name      = model_name + '_' + str(global_simu_id)

    ### Launch simulation
    ### NB : Don't set shell=True because then it is not possible to interact with the process inside the shell
    socket_id = "celinebateaukessler."+simu_name # has to be unique
    #--> TODO replace with DEVS+username+simu_name
    # using the user name as a prefix is a convention on PythonAnywhere

    cmd = ['python2.7', devsimpy_nogui, abs_model_filename, str(sim_duration), socket_id]
    fout = open(simu_name+'.out', 'w+') # where simulation execution report will be written
    flog = open(simu_name+'.log', 'w+') # where simulation execution report will be written
    process = subprocess.Popen(cmd, stdout=fout, stderr=flog, close_fds=True)
    # Call to Popen is non-blocking, BUT, the child process inherits the file descriptors from the parent,
    # and that will include the web app connection to the WSGI server,
    # so the process needs to run and finish before the connection is released and the server notices that the request is finished.
    # This is solved by passing close_fds=True to Popen

    # Check for an exception at initialization
    time.sleep(0.5)
    update_status(simu_name)

    # Store all data and process for this simulation
    global_running_sim[simu_name] = {
        'data' : {
            'model_filename'    : model_filename,
            'simulated_duration': sim_duration,
            'username'          : "celinebateaukessler",#TODO
            'creation_date'     : datetime.strftime(datetime.today(), "%Y-%m-%d %H:%M:%S"),
            'output_filename'   : simu_name+'.out',
            'log_filename'      : simu_name+'.log',
            'status'            : "RUNNING"},
        'process': process }

    # TODO data could be stored in a DB

    return {'success': True, simu_name : global_running_sim[simu_name]['data']}

#    Simulation pause / resume :
#    suspends / resumes the simulation thread but not the wrapping process
#    (to be called before parameters modification)
############################################################################

@route('/simulations/<simu_name>/pause', method=['PUT'])
@enable_cors
def pause(simu_name):
    """
    """
    return pause_or_resume (simu_name, 'PAUSE')


@route('/simulations/<simu_name>/resume', method=['PUT'])
@enable_cors
def resume(simu_name):
    """
    """
    return pause_or_resume (simu_name, 'RESUME')

#   Simulation kill
############################################################################
@route('/simulations/<simu_name>/kill', method=['PUT'])
@enable_cors
def kill(simu_name):
    """
    """
    status = update_status(simu_name)

    if 'UNKNOWN' in status:
        return {'success':False, 'info':status}
    if 'FINISHED' in status:
        return {'success':True, 'info':status}

    global_running_sim[simu_name]['process'].send_signal(signal.SIGKILL)
    return {'success':True, 'info':"KILLED"}

###    Simulation process pause (TBC)
############################################################################

@route('/simulations/<simu_name>/process_pause', method=['PUT'])
@enable_cors
def process_pause(simu_name):
    """
    """
    status = update_status(simu_name)

    if 'UNKNOWN' in status:
        return {'success':False, 'info':status}
    if 'FINISHED' in status:
        return {'success':False, 'info':status}

    global_running_sim[simu_name]['process'].send_signal(signal.SIGSTOP)
    global_running_sim[simu_name]['data']['status'] = "PROCESS_PAUSE"
    return {'success':True, 'info':"PROCESS_PAUSED"}


###    Simulation process resume (TBC)
############################################################################

@route('/simulations/<simu_name>/process_resume', method=['OPTIONS', 'GET'])
@enable_cors
def process_resume(simu_name):
    """
    """
    status = update_status(simu_name)

    if 'UNKNOWN' in status:
        return {'success':False, 'info':status}
    if 'FINISHED' in status:
        return {'success':False, 'info':status}

    global_running_sim[simu_name]['process'].send_signal(signal.SIGCONT)
    global_running_sim[simu_name]['data']['status'] = "RUNNING"
    return {'success':True, 'info':"PROCESS_RESUMED"}


############################################################################
#    RESOURCE = SIMULATION PARAMETERS
############################################################################
#    Update parameters of 1 block
#    body example :
### example POST body : {"modelID":"A2", "paramName":"maxValue", "paramValue":"50"}
############################################################################

@route('/simulations/<simu_name>/blocks/<block_label>', method=['PUT'])
@enable_cors
def modify(simu_name, block_label):
    """
    """
    status = update_status(simu_name)

    if 'UNKNOWN' in status:
        return {'success':False, 'info':status}
    if status != "PAUSED":
        return {'success':False, 'info':status}

    data = request.json
    global_data = {'block_label': block_label, 'block' : data}
    status = send_via_socket(simu_name, json.dumps(global_data))
    return {'success': True, 'status':status}


############################################################################
#   RESOURCE = SIMULATION RESULTS
############################################################################
#   Simulation report : includes results collection
############################################################################

@route('/simulations/<simu_name>/results', method=['GET'])
@enable_cors
def simulation_results(simu_name):

    status = update_status(simu_name)

    if 'UNKNOWN' in status:
        return {'success':False, 'info':status}
    if 'FINISHED' not in status:
        return {'success':False, 'info':status}

    fout=open(global_running_sim[simu_name]['data']['output_filename'], 'r')
    output = ""
    for line in fout:
        output = output + line
    fout.close()

    return {'success':True, 'results':output}


#   Simulation result as a (time, value) table
############################################################################
@route('/simulations/<simu_name>/results/<result_filename>', method=['GET'])
@enable_cors
def simulation_time_value_result(simu_name, result_filename):
    """
    """
    status = update_status(simu_name)

    if 'UNKNOWN' in status:
        return {'success':False, 'info':status}
    if 'FINISHED' not in status:
        return {'success':False, 'info':status}

    # Build the diagram data as :
    # - 1 list of labels (X or Time axis) called category TBC : what if time delta are not constant???
    # - 1 list of values (Y or Amplitude axis) called data
    result = []
    # TODO add check on file validity
    with open(os.path.join(yaml_path_dir, result_filename)) as fp:
        for line in fp:
            t,v = line.split(" ")
            result.append({"time":t, "value":v.rstrip('\r\n')})

    return json.dumps(result)

#   Simulation logs
############################################################################
@route('/simulations/<simu_name>/logs', method=['GET'])
@enable_cors
def simulation_logs(simu_name):

    status = update_status(simu_name)

    if 'UNKNOWN' in status:
        return {'success':False, 'info':status}

    flog=open(global_running_sim[simu_name]['data']['log_filename'], 'r')
    output = ""
    for line in flog:
        output = output + line
    flog.close()

    return {'success':True, 'logs':output}


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
