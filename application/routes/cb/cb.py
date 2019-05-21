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
@cb_bp.route('/cb/hosts', methods=['GET'])
@fresh_login_required
def hosts():
    '''
    This is the hosts page. This will include all of the hosts
    that were obtained from the CB server.
    '''
    # Query mongo for all of the hosts.
    results = mongo.get_all_cb_hosts()

    # This will set results to False if there was no
    # existing entry in the database.
    if len(results) == 0:
        results = False

    # Records log entry.
    main.record_log(request.path,
                    request.remote_addr,
                    'Viewed CB Hosts page.')

    # Returns the CB Run template.
    return render_template('/cb_hosts.html',
                            title="CB Hosts",
                            user=session,
                            hosts=results)

@cb_bp.route('/cb/refresh_host_list', methods=['GET', 'POST'])
@fresh_login_required
def refresh_host_list():
    '''
    This function will update the host list with the most current
    host list.
    '''
    # Collect all of the necessary information to add
    # details to the database.
    task = dict()

    task['name'] = 'Refresh Host List'
    task['task'] = 'job'
    task['type'] = 'Refresh Host List'
    task['owner'] = session['email']
    task['uuid'] = session['id']
    task['cuid'] = 0
    task['tuid'] = mongo.get_largest_tuid() + 1
    task['created'] = datetime.datetime.utcnow()
    task['expiration'] = task['created'] + datetime.timedelta(days=7)
    task['total_hosts'] = 0
    task['completed_hosts'] = 0
    task['active'] = True

    # Get the path to the 'update_hosts.py' script
    script_path = '{}/update_hosts.py'.format(app.config['LIBRARIES_DIRECTORY'])
    # script_path = script_path.replace(' ','\ ')
    
    # Runs a subprocess
    process = subprocess.Popen(['python', script_path, str(task['tuid'])], shell=False)

    # Assign the process id to the task object.
    task['pid'] = process.pid

    # Tell MongoDB to add task to the collection
    mongo.add_task(task)

    # Records log entry.
    main.record_log(request.path,
                    request.remote_addr,
                    'Created job: "Refresh Host List"')

    # Returns the CB Run template.
    return redirect(url_for('cb.hosts'))

@cb_bp.route('/cb/run', methods=['GET', 'POST'])
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
        cuid = request.form['input_sweep_type'].split('|')[0]
        input_flag = (request.form['input_sweep_type'].split('|')[1]).upper()

        # Collect sweep information from the Mongo DB.
        command_data = mongo.get_one_command(cuid)

        # Set up the sweep object.
        sweep['name'] = request.form['input_sweep_name']
        sweep['task'] = 'sweep'
        sweep['type'] = command_data['name']
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

        # This section is to take in the inputs that are not
        # required.
        if input_flag == "TRUE":
            sweep['file_name'] = request.form['input_file_name']
            # Runs a subprocess
            process = subprocess.Popen(['python',
                                        script_path,
                                        str(sweep['tuid']),
                                        sweep['file_name']],
                                        shell=False)
        else:
            # Runs a subprocess
            process = subprocess.Popen(['python',
                                        script_path,
                                        str(sweep['tuid'])],
                                        shell=False)

        # Assign the process id to the task object.
        sweep['pid'] = process.pid

        # Tell MongoDB to add task to the collection
        mongo.add_task(sweep)

        # Records log entry.
        message = 'Created sweep: {} (Task #{})'.format(sweep['name'], sweep['tuid'])
        main.record_log(request.path,
                        request.remote_addr,
                        message)

        # Return template with user created
        return render_template('/cb_run.html',
                        title="CB Run Sweep",
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
                        'Viewed CB Run Sweep page.')

        # Returns the CB Run template.
        return render_template('/cb_run.html',
                                title="CB Run Sweep",
                                sweeps=sweeps,
                                user=session)

@cb_bp.route('/cb/server_settings', methods=['GET', 'POST'])
@fresh_login_required
def server_settings():
    '''
    This is the Server Configuration page. This will contain all of
    the Carbon Black's server configuration settings so that
    you can perform sweeps against.
    '''
    # Gets the CB Server Configuration
    mongo_settings = mongo.get_server_settings()

    # Checks to see if it's a POST or GET request.
    if request.method == 'POST':
        # Get all variables input by the user.
        new_settings = dict()
        new_settings['root_url'] = request.form['input_root_url']
        new_settings['api_key'] = request.form['input_api_key']
        new_settings['connector_id'] = request.form['input_connector_id']
        new_settings['max_sessions'] = request.form['input_max_sessions']

        # Gets the CB Server Configuration
        existing_settings = mongo.get_server_settings()

        # Checks if the value is the same or different. If same,
        # then it will not do anything and will return true.
        results = list()
        results.append(check_if_same(existing_settings['_id'],
                                     'root_url',
                                     new_settings['root_url'],
                                     existing_settings['root_url']))
        results.append(check_if_same(existing_settings['_id'],
                                     'api_key',
                                     new_settings['api_key'],
                                     existing_settings['api_key']))
        results.append(check_if_same(existing_settings['_id'],
                                     'connector_id',
                                     new_settings['connector_id'],
                                     existing_settings['connector_id']))
        results.append(check_if_same(existing_settings['_id'],
                                     'max_sessions',
                                     new_settings['max_sessions'],
                                     existing_settings['max_sessions']))

        # If any of the configuration settings changed, it will record
        # it in the logs.
        if False in results:
            # Get new CB settings
            mongo_settings = mongo.get_server_settings()

            # Records log entry.
            message = 'Successfully updated the CB Server Configuration.'
            main.record_log(request.path,
                            request.remote_addr,
                            message)

            # Return CB Server Configuration template.
            return render_template('/cb_server_config.html',
                                    title="CB Server Configuration",
                                    type="success",
                                    value=message,
                                    user=session,
                                    settings=mongo_settings)
        
        else:
            message = 'No changes made to the CB Server Configuration. Nothing was updated.'
            # Return CB Server Configuration template.
            return render_template('/cb_server_config.html',
                                    title="CB Server Configuration",
                                    type="info",
                                    value=message,
                                    user=session,
                                    settings=mongo_settings)

    # If it's not a POST request, it will most likely be
    # a GET request. Just return the login template.
    else:

        # Gets the CB Server Configuration
        results = mongo.get_server_settings()
        
        # Records log entry.
        main.record_log(request.path,
                        request.remote_addr,
                        'Viewed the CB Server Configuration page.')

         # Return CB Server Configuration template.
        return render_template('/cb_server_config.html',
                                title="CB Server Configuration",
                                user=session,
                                settings=mongo_settings)

@cb_bp.route('/cb/sweep_history', methods=['GET'])
@fresh_login_required
def sweep_history():
    '''
    This is the sweep history page. This will get all of the previous
    sweep runs and their current status.
    '''
    # Records log entry.
    main.record_log(request.path,
                    request.remote_addr,
                    'Viewed CB Sweep History page.')

    # Define results variable
    results = list()

    # Query mongo for all of the sweeps.
    temp_results = mongo.get_all_sweeps()

    # This will set results to False if there was no
    # existing entry in the database.
    if len(temp_results) == 0:
        results = False

        # Returns the CB Sweep History template.
        return render_template('/cb_history.html',
                                title="CB Sweep History",
                                user=session,
                                history=results)
        
    # Calculate all percentages before passing data over
    # and assign it to a new list.
    for item in temp_results:
        # Clean up some of the data.
        item['created'] = item['created'].strftime("%B %d, %Y  %-I:%M:%S%p UTC")

        try:
            item['percentage_complete'] = int((item['completed_hosts'] / item['total_hosts']) * 100)
        
        except ZeroDivisionError:
            item['percentage_complete'] = 100

        results.append(item)

    # Returns the CB Sweep History template.
    return render_template('/cb_history.html',
                            title="CB Sweep History",
                            user=session,
                            history=results)

#########################################
#            OTHER FUNCTIONS            #
#########################################
def check_if_same(_id, data_type, new, existing):
    '''
    This function checks if the new and the current values
    are the same or not. If they are not the same, then it
    will update the record in the MongoDB database collection.

    :param _id:
    :param data_type:
    :param new:
    :param existing:
    :return True/False:
    '''

    if new != existing:
        mongo.update_server_settings(_id, data_type, new)
        return False
    
    else:
        return True