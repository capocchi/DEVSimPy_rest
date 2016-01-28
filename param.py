import os

############################################### set by the user
url_server = ""
port_server = None

current_path = os.path.dirname(__file__)
devsimpy_dir = 'devsimpy'
devsimpy_version_dir = 'version-2.9'

yaml_path_dir = os.path.join(current_path, 'static', 'yaml')
dsp_path_dir = os.path.join(current_path, 'static', 'dsp')

devsimpy_nogui = os.path.join(os.getcwd(), devsimpy_dir, devsimpy_version_dir, 'devsimpy-nogui.py')
##################################################