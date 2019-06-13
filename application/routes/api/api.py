import json
import os
import subprocess
import datetime
import time

import requests
from flask import Blueprint, redirect, request, session
from flask_login import LoginManager, current_user, fresh_login_required

from application import app
from application.libraries import password as passwd
from application.libraries import mongo
from application.routes import auth, main

#########################################
#        WEB ROUTE CONFIGURATION        #
#########################################
# Configurationuring the blueprint path for Flask to use.
api_bp = Blueprint('api', __name__, template_folder='/templates')

# Setting up Login Manager with Flask_Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.refresh_view = 'login'
login_manager.session_protection = 'strong'
login_manager.needs_refresh_message = 'To view protected pages, please re-authenticate.'
login_manager.needs_refresh_message_category = 'info'


#########################################
#              API FUNCTIONS            #
#########################################
@api_bp.route('/api/v1/get/case/name', methods=['GET'])
@fresh_login_required
def api_get_case_name():
    '''
    API call to get a count of all the hosts.
    '''

    # Query mongo for all of the hosts.
    results = mongo.get_one_case()

    # Return the number of hosts.
    return str(results['case'])

@api_bp.route('/api/v1/get/diskutil', methods=['GET'])
@fresh_login_required
def api_get_diskutil():
    '''
    API call to get a count of all the hosts.
    '''

    # Query the system for the disk utilization
    # statistics by using the 'df' command.
    df = subprocess.Popen(["df","-h"], stdout=subprocess.PIPE)

    # Since multiple lines can be returned, we
    # want root folder.
    for line in df.stdout:
        # Split each element of the results.
        splitline = line.decode().split()

        # If the line that we are looking at is the
        # root directory, return that data.
        if splitline[5] == '/':
            return splitline[4]
    
    # If nothing works, return N/A.
    return 'N/A'

@api_bp.route('/api/v1/get/hosts/all/count', methods=['GET'])
@fresh_login_required
def api_hosts_all():
    '''
    API call to get a count of all the hosts.
    '''

    # Query mongo for all of the hosts.
    results = mongo.get_all_cb_hosts()

    # Return the number of hosts.
    return str(len(results))

@api_bp.route('/api/v1/get/hosts/all/data', methods=['GET'])
@fresh_login_required
def api_hosts_all_data():
    '''
    API call to get a count of all the hosts.
    '''

    # Query mongo for all of the hosts.
    results = mongo.get_all_cb_hosts()

    # Go through each item and delete stuff we do not
    # need to return
    for item in results:
        del item['_id']
        del item['policy_name']

        # Clean up some of the data.
        item['last_reported_time'] = item['last_reported_time'].strftime("%B %d, %Y  %-I:%M:%S%p UTC")

    # Return the number of hosts.
    return json.dumps(results)

@api_bp.route('/api/v1/get/tasks/sweeps/all/count', methods=['GET'])
@fresh_login_required
def api_sweeps_all():
    '''
    API call to get a count of all the sweeps.
    '''

    # Query mongo for all of the hosts.
    results = mongo.get_all_sweeps()

    # Return the number of hosts.
    return str(len(results))

@api_bp.route('/api/v1/get/tasks/sweeps/active/count', methods=['GET'])
@fresh_login_required
def api_sweeps_active():
    '''
    API call to get count of all active sweeps.
    '''

    # Query mongo for all of the hosts.
    results = mongo.get_all_sweeps_active()

    # Return the number of hosts.
    return str(len(results))          

@api_bp.route('/api/v1/get/tasks/jobs/all/count', methods=['GET'])
@fresh_login_required
def api_jobs_all():
    '''
    API call to get a count of all the sweeps.
    '''

    # Query mongo for all of the hosts.
    results = mongo.get_all_jobs()

    # Return the number of hosts.
    return str(len(results))

@api_bp.route('/api/v1/get/tasks/all/data', methods=['GET'])
@fresh_login_required
def api_tasks_all():
    '''
    API call to get a count of all the sweeps.
    '''
    # Query mongo for all of the tasks
    results = mongo.get_all_tasks()

    # Go through each item and delete stuff we do not
    # need to return
    for item in results:
        del item['_id']
        del item['expiration']
        del item['pid']
        del item['uuid']

        # Clean up some of the data.
        item['created'] = item['created'].strftime("%B %d, %Y  %-I:%M:%S%p UTC")

        # Add percentage to each.
        try:
            item['percentage_complete'] = int((item['completed_hosts'] / item['total_hosts']) * 100)
        except:
            item['percentage_complete'] = 100

    # Return the data for all of the tasks
    return json.dumps(results)

@api_bp.route('/api/v1/get/tasks/jobs/host_list/last_updated', methods=['GET'])
@fresh_login_required
def api_host_list_last_updated():
    '''
    API call to get a the last updated timestamp of
    the host refresh list.
    '''

    # Query mongo for all of the hosts.
    results = mongo.get_all_host_list_refresh_job()

    # Checks if there are no results. Then it was never updated.
    if len(results) == 0:
        timestamp = "N/A"

    # Parse out the timestamp
    else:
        # timestamp = results[0]['created'].strftime("%Y-%m-%d %H:%M:%S")
        timestamp = results[0]['created'].strftime("%B %d, %Y  %-I:%M %p UTC")

    # Return the number of hosts.
    return str(timestamp)

@api_bp.route('/api/v1/get/gif', methods=['GET'])
@fresh_login_required
def api_get_gif():
    '''
    This function will return a link to a gif.

    :return url:
    '''
    # Query MongoDB for the Giphy settings.
    giphy_settings = mongo.get_giphy_settings()

    # Assign the values accordingly to request data.
    url = giphy_settings['root_url']
    parameters = {"api_key": giphy_settings['api_key'],
                  "rating": giphy_settings['rating']}

    # Send request to Giphy for a link.
    results = requests.get(giphy_settings['root_url'],
                           params=parameters)

    # Parse the data to extract just the link
    if results.status_code == 200:
        # Data unparsed
        data = json.loads(results.text)

        # Return just the link that we need.
        return data['data']['images']['downsized']['url']

@api_bp.route('/api/v1/get/alerts/user', methods=['GET'])
@fresh_login_required
def api_get_alerts():
    '''
    This function will return a list of all the alerts.

    :return alerts:
    '''
    # Query MongoDB for all of the alerts for
    # a specific user.
    alerts = mongo.get_all_alerts_active_user(session['email'])

    # Remove all of the "unnecessary" data before
    # sending to the client.
    for item in alerts:
        del item['_id']
        del item['active']
        del item['created']
        del item['owner']

    # Returns a list of all the alerts.
    return json.dumps(alerts)

@api_bp.route('/api/v1/get/users/all', methods=['GET'])
@fresh_login_required
def api_get_users():
    '''
    This function will get all of the users registered.
    '''

    # Query MongoDB for all of the users.
    results = mongo.get_all_users()

    # Go through all users and remove values we do not
    # need to pass to the user.
    for item in results:
        del item['_id']
        del item['active']
        del item['avatar']
        del item['last_logon']
        del item['last_password_change']
        del item['registration_date']
        del item['password']
        del item['theme_color']
 
    # Return the data for all of the tasks
    return json.dumps(results)

@api_bp.route('/api/v1/update/alert/<auid>', methods=['GET'])
@fresh_login_required
def api_update_alert(auid):
    '''
    This function will update the alert to false. This means
    that the user has already seen this alert.
    '''
    # Query MongoDB for a specific alert based on the AUID.
    alert_data = mongo.get_one_alert('auid', int(auid))

    # Update the alert to false.
    mongo.update_alert_id(alert_data['_id'], 'active', False)

    # Returns home. Need to return to page before.
    return redirect(request.referrer)

@api_bp.route('/api/v1/update/user/<uuid>/password', methods=['GET'])
@fresh_login_required
def api_reset_user_password(uuid):
    '''
    This function will reset a user's password
    '''

    # Checks if the user is an admin to show this
    # page or not.
    if session['account_type'] == 'admin':

        # Query MongoDB for the user's information.
        user_data = mongo.get_one_user_info('uuid', int(uuid))

        # If we have a user account, let's reset
        # the user's password.
        if user_data is not None:
            
            # Reset the user's password to a default password.
            hashed_password = passwd.hash(app.config['DEFAULT_PASSWORD'])

            # Change session variable information
            time_now = datetime.datetime.utcnow()
            session['last_password_change'] = time_now

            # Update the user data in the MongoDB with the accurate time.
            mongo.update_user_info(user_data['_id'], 'last_password_change', time_now)
            mongo.update_user_info(user_data['_id'], 'password', hashed_password.decode())

            # Create SFTP account for the user.
            create_sftp(user_data['email'], app.config['DEFAULT_PASSWORD'])
            
            # Record log entry
            message = 'Admin user "{}" reset password for "".'.format(session['email'], user_data['email'])

            main.record_log(request.path,
                            request.remote_addr,
                            message)

            return redirect(request.referrer)

@api_bp.route('/api/v1/stop/task/<tuid>', methods=['GET'])
@fresh_login_required
def stop_task(tuid):
    '''
    This function will stop a task given the TUID.
    '''
    # Query MongoDB for the one alert given the TUID.
    task_object = mongo.get_one_task('tuid', int(tuid))

    # Checks to see if the task is active before trying
    # to kill/terminate it.
    if task_object['active']:

        # Despite us knowing that the process exists and it
        # will attempt to kill the process, let's add this
        # try-except catch, just in case.
        try:
            os.kill(task_object['pid'], 9)
        except:
            pass

    # Update the data in the task.
    mongo.update_task('active', False, task_object['_id'])

    # Records log entry.
    main.record_log(request.path,
                    request.remote_addr,
                    'Stopped Task ID: {}.'.format(tuid))

    # Returns to where the user was before. Referrer page.
    return redirect(request.referrer)

@api_bp.route('/api/v1/restart/task/<tuid>', methods=['GET'])
@fresh_login_required
def restart_task(tuid):
    '''
    This function will restart a task given the TUID.
    '''
    # Query MongoDB for the one alert given the TUID.
    task_object = mongo.get_one_task('tuid', int(tuid))

    # Checks to see if the task is active before trying
    # to kill/terminate it.
    if task_object['active']:

        # Despite us knowing that the process exists and it
        # will attempt to kill the process, let's add this
        # try-except catch, just in case.
        try:
            os.kill(task_object['pid'], 9)
        except:
            pass

    # Get the path to the 'update_hosts.py' script
    script_path = '{}/sweeper.py'.format(app.config['LIBRARIES_DIRECTORY'])
    # script_path = script_path.replace(' ','\ ')

    # Extract command_type in order to determine the command
    # type so that we can send the proper command over.
    command_type = mongo.get_command_type(cuid)
    
    # This section is to take in the inputs that are not
    # required.
    if command_type == 3:
        # Runs a subprocess
        process = subprocess.Popen(['python3',
                                    script_path,
                                    app.config['OUTPUT_DIRECTORY'],
                                    str(task_object['tuid']),
                                    task_object['file_name']],
                                    shell=False)

    elif command_type == 2:
        # Runs a subprocess
        process = subprocess.Popen(['python3',
                                    script_path,
                                    app.config['OUTPUT_DIRECTORY'],
                                    str(task_object['tuid']),
                                    task_object['file_name'],
                                    task_object['command_run']],
                                    shell=False)

    else:
        # Runs a subprocess
        process = subprocess.Popen(['python3',
                                    script_path,
                                    app.config['OUTPUT_DIRECTORY'],
                                    str(task_object['tuid'])],
                                    shell=False)

    # Assign the process id to the task object.
    new_pid = process.pid

    # Update the data in the task.
    mongo.update_task('pid', int(new_pid), task_object['_id'])
    mongo.update_task('active', True, task_object['_id'])

    # Records log entry.
    main.record_log(request.path,
                    request.remote_addr,
                    'Restarted Task ID: {}.'.format(tuid))

    # Returns to where the user was before. Referrer page.
    return redirect(request.referrer)



#########################################
#            OTHER FUNCTIONS            #
#########################################
def create_sftp(email, password):
    '''
    Creates an SFTP account for a newly registered user.
    '''

    # Command to create user and add to the 'sftp' group.
    add_user = subprocess.Popen(["sudo", "useradd", "-M", email, "-g", "sftp"])
    time.sleep(2)

    # Change user's password.
    change_password_proc = subprocess.Popen(["sudo", "passwd", email], stdin=subprocess.PIPE)
    time.sleep(1)

    # Generate password format.
    password = ('{}\n'.format(password)).encode()

    # Provide password when requested.
    change_password_proc.stdin.write(password)
    time.sleep(1)
    change_password_proc.stdin.write(password)
    time.sleep(1)

    # Flush the screen
    change_password_proc.stdin.flush()