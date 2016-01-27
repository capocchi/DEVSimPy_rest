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
proc_sim_dict = {}

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
    return static_file('index.html', root=os.path.join(current_path, 'static'))

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

def getYAML(name):
    """ Get Yaml description from file name
    """

@route('/info', method=['OPTIONS', 'GET'])
@enable_cors
def recipes_info():
    """ Get server info
    """
    from platform import python_version

    data = {'devsimpy-version':os.path.basename(os.path.dirname(python_file)),
            'devsimpy-libraries': filter(lambda a: a not in [".directory", "Basic", "__init__.py"], os.listdir(os.path.join(os.path.dirname(python_file), 'Domain'))),
            'python-version': python_version(),
            ### TODO read __init__.py to build plugins list
            'devsimpy-plugins':filter(lambda a: a not in ["__init__.py"], os.listdir(os.path.join(os.path.dirname(python_file), 'plugins'))),
            'url-server':url_server,
            'machine-server': subprocess.check_output("uname -m", shell=True),
            'os-server': subprocess.check_output("uname -o", shell=True),
            'machine-version-server': subprocess.check_output("uname -v", shell=True)
            }

    return data

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

@route('/yaml/save', method=['OPTIONS', 'POST'])
@enable_cors
def save_yaml():
    """ Update yaml file from devsimpy-mob
    """
    data = request.json

    yaml = data['filename']
    model = data['model']
    args = data['args']

    yaml_path = os.path.join(yaml_path_dir, yaml)

    ### update filename abs path
    data['filename'] = yaml_path

    obj = json.dumps(data) # JSON to string

    #try:

    ### command to be execut
    cmd = "python2.7 "+python_file+" -update "+"\""+str(obj.replace("\"","'"))+"\""

    ### transformation completed (output is json format)
    output = subprocess.check_output(cmd, shell=True)

    return {'success':True, 'cmd':cmd, 'output':output}

    #except: Si on traite l'exception ici on n'a plus le rapport dans la reponse

        #return {'success':False}

### lcapocchi.pythonanywhere.com/yaml/labels?name=test1.yaml
@route('/yaml/labels', method=['OPTIONS', 'GET'])
@enable_cors
def labels_yaml():
    """ get the models block list of yaml
    """
    ### get param coming from url
    name_param = request.params.name

    try:

        ### command to be execut
        cmd = "python2.7 "+python_file+" -models "+os.path.join(yaml_path_dir, name_param)

        ### transformation completed (output is json format)
        output = subprocess.check_output(cmd, shell=True)

        return {'success':True, 'output':eval(output.rstrip('\r\n'))}

    except:

        return {'success':False, 'cmd':cmd}

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
        cmd = ["python2.7", python_file, dsp_file,"-json"]

        ### transformation completed (output is json format)
        output = subprocess.check_output(cmd)

    else:
        ### generation failed
        output = {'success':False, 'info': "file does not exist!"}

    return output

### simulate the dsp file
### /simulate?name=test.dsp&time=10
### or /simulate?name=test.yaml&time=10
@route('/simulate', method=['OPTIONS', 'GET'])
@enable_cors
def simulate():
    """
    """
    ### get param coming from url
    name_param = request.params.name
    time_param = request.params.time

    dateStart = datetime.strftime(datetime.today(), "%Y-%m-%d %H:%M:%S:%f")

    ### if no time limit and .dsp or .yaml file, we can simulate
    if name_param.endswith(('.dsp', '.yaml')):

        if time_param in ('ntl', 'inf'):
            time_param = "10000000"

        if time_param.isdigit():

            ### path dir of model and .dat
            path = dsp_path_dir if name_param.endswith('.dsp') else yaml_path_dir

            ### delete old .dat ofr the model
            for name in filter(lambda fn: fn.endswith('.dat') and fn.split('_')[0] == os.path.splitext(name_param)[0], os.listdir(path)):
                os.remove(os.path.join(path, name))

            ### dsp or yaml file
            dsp_file = os.path.join(path, name_param)

            ### command to be executed
            ### if the command is a string, it can only be executed with shell=True option
            ### and then it is not possible to interact with the process
            cmd = ['python2.7', python_file, dsp_file, str(time_param)]

            ### launch simulation
            try:
                fout = open('simuout.dat', 'w+')
                #fin = open('user.in', 'w+')
                fin = open('user.in', 'w')
                fin.close()
                process = subprocess.Popen(cmd, stdout=fout, stderr=subprocess.STDOUT, close_fds=True)
                # Call to Popen is non-blocking, BUT, the child process inherits the file descriptors from the parent,
                # and that will include the web app connection to the WSGI server,
                # so the process needs to run and finish before the connection is released and the server notices that the request is finished.
                # This is solved by passing close_fds=True to Popen
                proc_sim_dict[name_param] = {'process':process, 'output':fout, 'output_name':'simuout.dat', 'inputname':'user.in'}

                return {'success':True}
            except:
                return {'success':False, 'info': 'error processing '+cmd[0]+' '+cmd[1]+' '+cmd[2]+' '+cmd[3]}

        else:
            ### simulation failed
            return {'success':False, 'info': "time must be digit!"}
    else:
        ### simulation failed
        return {'success':False, 'info': "file does not exist!"+request.params.name}

    #return {'dateStart':dateStart, 'dateStop': datetime.strftime(datetime.today(), "%Y-%m-%d %H:%M:%S:%f")}
    #return output

@route('/modify', method=['POST'])
@enable_cors
def modify():
    #return request.params
    data = request.json
    simu_name = data['simulation_name']
    if (proc_sim_dict.has_key(simu_name)):
        #fin = proc_sim_dict[simu_name]['input'] !!! not working ???
        fin = open(proc_sim_dict[simu_name]['inputname'], 'a')
        del data['simulation_name']
        data['date'] = datetime.strftime(datetime.today(), "%Y-%m-%d %H:%M:%S:%f")
        fin.write(json.dumps(data))
        fin.close()
        return "Modification done "
    else:
        return "no simulation in progress named " + simu_name

@route('/result', method=['OPTIONS', 'GET'])
@enable_cors
def result():
    name_param = request.params.name
    #TODO verif process fini
    fout = proc_sim_dict[name_param]['output']
    if fout.closed: fout=open('simuout.dat', 'r')# stocker le nom du fichier dans le dictionnaire ou BD SQLite
    output = ""
    fout.seek(0,0)
    for line in fout:
        output = output + line
    fout.close()
    #TODO del dict_proc_sim
    return output

@route('/pause', method=['OPTIONS', 'GET'])
@enable_cors
def pause():
    """
    """
    ### get param coming from url
    name_param = request.params.name

    if (proc_sim_dict.has_key(name_param)):
        #try:
            process = proc_sim_dict[name_param]['process']
            #fout    = proc_sim_dict[name_param]['output']
            process.send_signal(signal.SIGSTOP)
            #fout.close()
            return "Simulation paused"
        #except Exception:
            #return str(Exception)
    else:
        return "no simulation in progress named " + name_param

@route('/resume', method=['OPTIONS', 'GET'])
@enable_cors
def resume():
    """
    """
    ### get param coming from url
    name_param = request.params.name
    #TODO test si le process est en pause
    if (proc_sim_dict.has_key(name_param)):
        try:
            process = proc_sim_dict[name_param]['process']
            #fout    = proc_sim_dict[name_param]['output']
            #fout = open('simuout.dat', a)
            process.send_signal(signal.SIGCONT)
            return "Simulation resumed"
        except Exception:
            return str(Exception)
    else:
        return "No simulation named " + name_param + " in progress"

@route('/kill', method=['OPTIONS', 'GET'])
@enable_cors
def kill():
    """
    """
    ### get param coming from url
    name_param = request.params.name
    #TODO test si le process est en pause
    if (proc_sim_dict.has_key(name_param)):
        try:
            process = proc_sim_dict[name_param]['process']
            process.send_signal(signal.SIGKILL)
            return "Simulation killed"
        except Exception:
            return str(Exception)
    else:
        return "No simulation named " + name_param + " in progress"


@route('/plot', method=['OPTIONS', 'GET'])
@enable_cors
def plot():
    """
    """
###    from bokeh.plotting import figure, output_server, show
###    output_server("line")
###    p = figure(plot_width=400, plot_height=400)
###    # add a line renderer
###    p.line([5, 2, 3, 4, 5], [5, 7, 2, 4, 5], line_width=2)
##    show(p)

    filename = request.params.name

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

#import psutil, time, subprocess

#cmd = "python target.py"
#P = subprocess.Popen(cmd,shell=True)
#psProcess = psutil.Process(pid=P.pid)

#while True:
#    time.sleep(5)
#    psProcess.suspend()
#    print 'I am proactively leveraging my synergies!'
#    psProcess.resume()


debug(True)
application = default_app()

if __name__ == "__main__":
    from paste import httpserver
    httpserver.serve(application, host=url_server, port=port_server)