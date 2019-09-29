import datetime
import json
import os
import subprocess

from application import app
from application.routes import main
from application.libraries import password as passwd
from application.libraries import mongo

from flask import Blueprint
from flask import request
from flask import render_template
from flask import redirect
from flask import session
from flask import url_for

from flask_login import LoginManager
from flask_login import fresh_login_required
from flask_login import logout_user
from flask_login import login_user

from werkzeug.utils import secure_filename

#########################################
#        WEB ROUTE CONFIGURATION        #
#########################################
# Configurationuring the blueprint path for Flask to use.
cb_bp = Blueprint('cb', __name__, template_folder='/templates')

# Setting up Login Manager with Flask_Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.refresh_view = 'login'
login_manager.session_protection = 'strong'
login_manager.needs_refresh_message = 'To view protected pages, please re-authenticate.'
login_manager.needs_refresh_message_category = 'info'


#########################################
#       WEB APPLICATION FUNCTIONS       #
#########################################
@cb_bp.route('/cb/build_sweep', methods=['GET', 'POST'])
@fresh_login_required
def build_sweep():
    '''
    This is the run sweep page. This will allow the user to set
    up a sweep to run against all the systems in the environment.
    '''

    # Checks to see if it's a POST or GET request.
    if request.method == 'POST':
        # Get all variables input by the user.
        sweep = dict()
        
        # Parse input data.
        sweep['command'] = request.form['input_command'].strip()
        sweep['command_type'] = 1
        sweep['created'] = datetime.datetime.utcnow()
        sweep['cuid'] = int(mongo.get_largest_cuid() + 1)
        sweep['description'] = request.form['input_description'].strip()
        sweep['device_type'] = request.form['input_device_type']
        sweep['modified'] = datetime.datetime.utcnow()
        sweep['name'] = request.form['input_name'].strip().title()
        sweep['output_file'] = request.form['input_output_file'].strip()
        sweep['owner'] = session['email']
        sweep['require_file'] = False
        sweep['require_input'] = False

        # Add record to the database.
        mongo.add_sweep(sweep)

        # Records log entry.
        message = 'Created new sweep type: {}'.format(sweep['name'])
        main.record_log(request.path,
                        request.remote_addr,
                        message)

        # Get all sweeps.
        sweeps = mongo.get_all_sweep_commands()

        # Return template with user created
        return render_template('/cb_build.html',
                        title="Build Sweep",
                        type="success",
                        value=message,
                        sweeps=sweeps,
                        user=session)

    # If it's not a POST request, it will most likely be
    # a GET request. Just return the login template.
    else:
        # Get all sweeps.
        sweeps = mongo.get_all_sweep_commands()

        # Records log entry.
        main.record_log(request.path,
                        request.remote_addr,
                        'Viewed Create Sweep page.')

        # Returns the CB Run template.
        return render_template('/cb_build.html',
                                title="Build Sweep",
                                sweeps=sweeps,
                                user=session)

@cb_bp.route('/cb/run_sweep', methods=['GET', 'POST'])
@fresh_login_required
def run_sweep():
    '''
    This is the run sweep page. This will allow the user to set
    up a sweep to run against all the systems in the environment.
    '''

    # Get all sweeps.
    sweeps = mongo.get_all_sweep_commands()

    # Checks to see if it's a POST or GET request.
    if request.method == 'POST':
        # Get all variables input by the user.
        sweep = dict()
        
        # Parse sweep information
        cuid = int(request.form['input_sweep_type'].split('|')[0])
        input_flag = (request.form['input_sweep_type'].split('|')[1]).upper()
        file_flag = (request.form['input_sweep_type'].split('|')[2]).upper()

        # Collect sweep information from the Mongo DB.
        command_data = mongo.get_one_command(cuid)

        # Set up the sweep object.
        sweep['name'] = request.form['input_sweep_name']
        sweep['task'] = 'sweep'
        sweep['type'] = command_data['name']
        sweep['command_run'] = command_data['command']
        sweep['owner'] = session['email']
        sweep['uuid'] = session['id']
        sweep['cuid'] = cuid
        sweep['tuid'] = mongo.get_largest_tuid() + 1
        sweep['created'] = datetime.datetime.utcnow()
        sweep['expiration'] = sweep['created'] + datetime.timedelta(days=7)
        sweep['total_hosts'] = 0
        sweep['completed_hosts'] = 0
        sweep['active'] = True

        # Get the path to the 'update_hosts.py' script
        script_path = '{}/sweeper.py'.format(app.config['LIBRARIES_DIRECTORY'])
        # script_path = script_path.replace(' ','\ ')

        # Extract command_type in order to determine the command
        # type so that we can send the proper command over.
        command_type = mongo.get_command_type(cuid)

        # This section is to take in the inputs that are not
        # required.
        if command_type == 3:
            sweep['file_name'] = (request.form['input_file_name']).strip()
            # Runs a subprocess
            process = subprocess.Popen(['python3',
                                        script_path,
                                        app.config['OUTPUT_DIRECTORY'],
                                        str(sweep['tuid']),
                                        sweep['file_name']],
                                        shell=False)

        elif command_type == 2:
            # Check if the file exists. We don't want to continue
            # if there isn't a file to be uploaded.
            if 'upload_file' not in request.files:
                # Return template with user created
                return render_template('/cb_run.html',
                                        title="Sweep",
                                        type="danger",
                                        value="You forgot to upload a file! Try again.",
                                        sweeps=sweeps,
                                        user=session)

            # Grab filename
            uploaded_file = request.files['upload_file']

            # Check if filename is not blank.
            if uploaded_file.filename == "":
                # Return template with user created
                return render_template('/cb_run.html',
                                        title="Sweep",
                                        type="danger",
                                        value="You forgot to upload a file! Try again.",
                                        sweeps=sweeps,
                                        user=session)

            # Save fipath.
            uploaded_filename = secure_filename(uploaded_file.filename)
            sweep['file_name'] = os.path.join(app.config['UPLOAD_DIRECTORY'], uploaded_filename)

            # Save file
            uploaded_file.save(sweep['file_name'])
            
            # Extract command to run.
            sweep['command_run'] = (request.form['input_command']).strip()

            # Runs a subprocess
            process = subprocess.Popen(['python3',
                                        script_path,
                                        app.config['OUTPUT_DIRECTORY'],
                                        str(sweep['tuid']),
                                        sweep['file_name'],
                                        sweep['command_run']],
                                        shell=False)

        else:
            sweep['file_name'] = ""
            # Runs a subprocess
            process = subprocess.Popen(['python3',
                                        script_path,
                                        app.config['OUTPUT_DIRECTORY'],
                                        str(sweep['tuid'])],
                                        shell=False)

        # Assign the process id to the task object.
        sweep['pid'] = process.pid

        # Tell MongoDB to add task to the collection
        mongo.add_task(sweep)

        # Records log entry.
        message = 'Created Sweep sweep: {} (Task #{})'.format(sweep['name'], sweep['tuid'])
        main.record_log(request.path,
                        request.remote_addr,
                        message)

        # Return template with sweep created
        return render_template('/cb_run.html',
                        title="Sweep",
                        type="success",
                        value=message,
                        sweeps=sweeps,
                        user=session)

    # If it's not a POST request, it will most likely be
    # a GET request. Just return the login template.
    else:
        # Records log entry.
        main.record_log(request.path,
                        request.remote_addr,
                        'Viewed Sweep page.')

        # Returns the CB Run template.
        return render_template('/cb_run.html',
                                title="Sweep",
                                sweeps=sweeps,
                                user=session)

@cb_bp.route('/cb/sweep_<tuid>', methods=['GET'])
@fresh_login_required
def sweep_details(tuid):
    '''
    This is the sweep history page. This will get all of the previous
    sweep runs and their current status.
    '''
    try:
        # Query mongo for all of the hosts.
        results = mongo.get_all_sweep_hosts(int(tuid))

        # Records log entry.
        main.record_log(request.path,
                        request.remote_addr,
                        'Viewed CB Sweep #{} details.'.format(tuid))

        sweep_name = (mongo.get_one_task('tuid', int(tuid)))['name']

        # This will set results to False if there was no
        # existing entry in the database.
        if len(results) == 0:
            results = False

        # Returns the CB Run template.
        return render_template('/cb_sweep_details.html',
                                title="Task History - Details",
                                user=session,
                                sweep_name=sweep_name,
                                hosts=results)
    
    except:
        return redirect(url_for('cb.sweep_history'))

#########################################
#            OTHER FUNCTIONS            #
#########################################
