import base64
import csv
import datetime
import subprocess
import json
import os
import re
import shutil

import requests
from flask import (Flask, Response, abort, jsonify, redirect, render_template,
                   request, send_file, send_from_directory, session, url_for)
from flask_login import (LoginManager, UserMixin, current_user,
                         fresh_login_required)
from werkzeug.utils import secure_filename

from application import app
from application.libraries import mongo
from application.routes.api.api import api_bp
from application.routes.auth.auth import auth_bp
from application.routes.cb.cb import cb_bp

#########################################
#     WEB APPLICATION CONFIGURATION     #
#########################################

# Registering Flask Blueprints
# app.register_blueprint(login_bp, url_prefix='/main/')
app.register_blueprint(auth_bp)
app.register_blueprint(cb_bp)
app.register_blueprint(api_bp)

# # Setting up Login Manager with Flask_Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.refresh_view = 'auth.login'
login_manager.session_protection = 'strong'
login_manager.needs_refresh_message = 'To view protected pages, please re-authenticate.'
login_manager.needs_refresh_message_category = 'info'


#########################################
#           CLASS DEFINITIONS           #
#########################################

# User class definition for CB Bot
class User(UserMixin):

    def __init__(self, dict_object):

        # Unique identifiers
        self.id = dict_object['uuid']

        # User personal information
        self.first_name = dict_object['first_name']
        self.last_name = dict_object['last_name']
        self.email = dict_object['email']
        self.avatar = dict_object['avatar']
        self.theme_color = dict_object['theme_color']

        # User account related data
        self.last_logon = dict_object['last_logon']
        self.registration_date = dict_object['registration_date']
        self.last_password_change = dict_object['last_password_change']
        self.account_type = dict_object['account_type']
        self.active = dict_object['active']
        self.authenticated = True

    def get_avatar(self):
        return self.avatar

    def get_fullname(self):
        return '%s %s' % (self.first_name, self.last_name)

    def get_id(self):
        return self.id

    def is_active(self):
        return self.active

    def is_authenticated(self):
        return self.authenticated


#########################################
#      MAIN WEB APPLICATION ROUTES      #
#########################################

@app.route('/', methods=['GET'])
@app.route('/home', methods=['GET'])
@fresh_login_required
def home():
    '''
    Home page for the site. Before we can grant access
    to just anyone, the '@fresh_login_required' function
    will force a user to be authenticated and establish
    a session, before being allowed to view this page.
    
    Once authenticated, session variables are assigned
    to then establish a persistent session throughout
    the duration of the user's session.
    '''

    # This will determine if a session is active, if so,
    # add Flasks' 'current_user' module to add all elements
    # to the session variable.
    if session.get('active') is None:
        session['active'] = current_user.active
        session['id'] = current_user.id
        session['first_name'] = current_user.first_name
        session['last_name'] = current_user.last_name
        session['avatar'] = current_user.avatar
        session['theme_color'] = current_user.theme_color
        session['email'] = current_user.email
        session['account_type'] = current_user.account_type
        session['authenticated'] = current_user.authenticated
        session['last_logon'] = current_user.last_logon
        session['last_password_change'] = current_user.last_password_change
        session['registration_date'] = current_user.registration_date

        # Records log entry.
        record_log(request.path,
                   request.remote_addr,
                   'User successfully authenticated.')

    # Records log entry.
    record_log(request.path,
               request.remote_addr,
               'Viewed the Home page.')

    # Get list of active tasks
    results = mongo.get_all_tasks_active()

    return render_template('/home.html',
                           title='Home',
                           tasks=results,
                           user=session)

@app.route('/activity_logs', methods=['GET'])
@fresh_login_required
def activity_logs():
    '''
    This is the activity logs page. Here we will present
    all of the logs for each individual user. If you are
    an admin, you will get all the logs from every user.
    '''

    # Records log entry.
    record_log(request.path,
               request.remote_addr,
               'Viewed the activity logs.')

    if session['account_type'] == 'admin':
        results = mongo.get_all_log_entries()
    
    else:
        results = mongo.get_all_user_log_entries(session['email'])

    # Return activity logs template.
    return render_template('/activity_logs.html',
                           title='Activity Logs',
                           logs=results,
                           user=session)

@app.route('/activity_logs/download', methods=['GET'])
@fresh_login_required
def activity_logs_download():
    '''
    This function will download the activities for the user.
    '''

    # Records log entry.
    record_log(request.path,
               request.remote_addr,
               'Downloaded activity logs.')

    # Deletes all of the files in the log directory.
    # This is just a cleanup function to make sure the
    # folder size does not get too large.
    delete_folder_contents(app.config['LOG_DIRECTORY'])

    # If user is an admin, user will see all logs for all users,
    # otherwise, the user will only see their logs.
    if session['account_type'] == 'admin':
        results = mongo.get_all_log_entries()
    else:
        results = mongo.get_all_user_log_entries(session['email'])

    # Creates a csv log file and returns the log path.
    log_file = generate_logs_csv(results)

    # Returns the file for download.
    return send_file(log_file, as_attachment=True)

@app.route('/endpoints', methods=['GET'])
@fresh_login_required
def endpoints():
    '''
    This is the hosts page. This will include all of the hosts
    that were obtained from the CB server.
    '''
    # Query mongo for all of the hosts.
    results = mongo.get_all_endpoints()

    # This will set results to False if there was no
    # existing entry in the database.
    if len(results) == 0:
        results = False

    # Records log entry.
    record_log(request.path,
                request.remote_addr,
                'Viewed Endpoints page.')

    # Returns the CB Run template.
    return render_template('/endpoints.html',
                            title="Endpoints",
                            user=session,
                            hosts=results)

@app.route('/refresh_host_list', methods=['GET', 'POST'])
@fresh_login_required
def refresh_host_list():
    '''
    This function will update the endpoint list with the most current
    endpoint list.
    '''
    # Collect all of the necessary information to add
    # details to the database.
    task = dict()

    task['name'] = 'Refresh Endpoint List'
    task['task'] = 'job'
    task['type'] = 'Refresh Endpoint List'
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
    process = subprocess.Popen(['python3', script_path, str(task['tuid'])], shell=False)

    # Assign the process id to the task object.
    task['pid'] = process.pid

    # Tell MongoDB to add task to the collection
    mongo.add_task(task)

    # Records log entry.
    record_log(request.path,
               request.remote_addr,
               'Created job: "Refresh Endpoint List"')

    # Returns the CB Run template.
    return redirect(url_for('endpoints'))

@app.route('/settings', methods=['GET', 'POST'])
@fresh_login_required
def settings():
    '''
    Settings page. This will include all of the configuration
    settings for the server. At the moment there aren't that
    many, but most likely as more modules get added, new API
    keys will need to be re-added.
    '''
    # Checks if the user is an admin to show this
    # page or not.
    if session['account_type'] == 'admin':
        # Checks if it was a POST request or not.
        if request.method == 'POST':

            # Let's validate what form are we looking at.
            update = request.form['config']
            if update == "giphy":
                new_settings = dict()
                new_settings['api_key'] = request.form['input_api_key']
                new_settings['rating'] = request.form['input_rating']

                # Gets the Giphy Configuration
                existing_settings = mongo.get_giphy_settings()

                # Checks if the value is the same or different. If same,
                # then it will not do anything and will return true.
                results = list()
                results.append(check_if_same(existing_settings['_id'],
                                            'api_key',
                                            new_settings['api_key'],
                                            existing_settings['api_key']))
                results.append(check_if_same(existing_settings['_id'],
                                            'rating',
                                            new_settings['rating'],
                                            existing_settings['rating']))
                
                if False in results:
                    message = 'Successfully updated the Giphy configuration.'
                    alert_type = "success"

                    # Record a log entry indicating what has been changed.
                    record_log(request.path,
                            request.remote_addr,
                            message)

                else:
                    message = 'No changes made to the configurations. Nothing was updated.'
                    alert_type = "info"

            elif update == "cb_data":
                new_settings = dict()
                new_settings['root_url'] = request.form['input_root_url']
                new_settings['api_id'] = request.form['input_api_id']
                new_settings['api_secret_key'] = request.form['input_api_secret_key']
                new_settings['min_check_in_time'] = request.form['input_min_check_in_time']
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
                                            'api_secret_key',
                                            new_settings['api_secret_key'],
                                            existing_settings['api_secret_key']))
                results.append(check_if_same(existing_settings['_id'],
                                            'min_check_in_time',
                                            new_settings['min_check_in_time'],
                                            existing_settings['min_check_in_time']))
                results.append(check_if_same(existing_settings['_id'],
                                            'api_id',
                                            new_settings['api_id'],
                                            existing_settings['api_id']))
                results.append(check_if_same(existing_settings['_id'],
                                            'max_sessions',
                                            new_settings['max_sessions'],
                                            existing_settings['max_sessions']))

                if False in results:
                    message = 'Successfully updated the CB configuration.'
                    alert_type = "success"

                    # Record a log entry indicating what has been changed.
                    record_log(request.path,
                            request.remote_addr,
                            message)
                
                else:
                    message = 'No changes made to the configurations. Nothing was updated.'
                    alert_type = "info"

            else:
                message = 'You did something bad. Not cool.'
                alert_type = "danger"

        else:
            # Since it's only a get request, just record
            # this log entry
            record_log(request.path,
                    request.remote_addr,
                    'Viewed the Settings page.')

        # Whether there is an update or not, I need to 
        # provide all of the settings back to the user.
        # Gets CB Bot configuration
        cb_data = mongo.get_server_settings()
        giphy_data = mongo.get_giphy_settings()

        # Checks if it's empty or not.
        if len(cb_data) == 0:
            cb_data = dict()
            cb_data['root_url'] = ""
            cb_data['api_id'] = ""
            cb_data['api_secret_key'] = ""
            cb_data['min_check_in_time'] = 3
            cb_data['max_sessions'] = 30

        # Checks if it's empty or not.
        if len(giphy_data) == 0:
            giphy_data = dict()
            giphy_data['api_key'] = ""
            giphy_data['rating'] = ""

        # Returns template without certain variables if it
        # is a GET request and not a POST request.
        if request.method == 'GET':
            return render_template('/settings.html',
                                title='Settings',
                                user=session,
                                giphy=giphy_data,
                                cb=cb_data)

        return render_template('/settings.html',
                            title='Settings',
                            type=alert_type,
                            value=message,
                            user=session,
                            giphy=giphy_data,
                            cb=cb_data)

    else:
        # Records log entry.
        record_log(request.path,
                    request.remote_addr,
                    'User attempted to access the Settings page. Forbidden.')
        
        # Redirect to home page.
        return redirect(url_for('home'))

@app.route('/tasks', methods=['GET'])
@fresh_login_required
def tasks():
    '''
    Task page. This will include all of the running jobs and
    sweeps in one page. Jobs for now are simple the "refresh
    Endpoint list" action item in the table.
    '''
    # results = list()

    # # Queries mongo for all of the tasks.
    # temp_results = mongo.get_all_tasks()

    # # Checks if it's empty or not.
    # if len(temp_results) == 0:
    #     results = False

    #     return render_template('/tasks.html',
    #                        title='Tasks',
    #                        user=session,
    #                        tasks=results)

    # Calculate all percentages before passing data over
    # and assign it to a new list.
    # for item in temp_results:
    #     try:
    #         item['percentage_complete'] = int((item['completed_hosts'] / item['total_hosts']) * 100)
        
    #     except ZeroDivisionError:
    #         item['percentage_complete'] = 100

    #     results.append(item)
    #     print(item)

    # Records log entry.
    record_log(request.path,
               request.remote_addr,
               'Viewed the Tasks page.')

    return render_template('/tasks.html',
                           title='Tasks',
                           user=session)

@app.route('/favicon.ico')
def favicon():
    '''
    This will return the favicon for the page.
    '''

    # Returns the favicon to every page loaded.
    return send_from_directory('static/images/',
                               'cb_bot_favicon.png',
                               mimetype='image/vnd.microsoft.icon')



#########################################
#         LOGIN MANAGER FUNCTIONS       #
#########################################
@login_manager.user_loader
def load_user(user_id):
    '''
    This function load a user by querying MongoDB
    database and getting user information and then
    creating a user object.

    :param: user_id
    :return: User object
    '''

    # Gets user data from MongoDB and returns a
    # User object.
    db_user = mongo.get_one_user_info("uuid", user_id)
    return User(db_user)

@login_manager.needs_refresh_handler
def refresh():
    return abort(400)


#########################################
#             ERROR HANDLERS            #
#########################################
@app.errorhandler(400)
def page_not_found(e):
    return Response('<p>Login failed</p>')

# Unauthorized Error Handling
@app.errorhandler(401)
def page_not_found(e):
    return redirect(url_for('auth.login'))

# Not Found Error Handling
@app.errorhandler(404)
def page_not_found(e):
    # Records log entry.
    record_log(request.path,
               request.remote_addr,
               'Page not found.')

    # Return 404 template.
    return render_template('/404.html')



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

def record_log(page, ip, message, user=None, account_type=None):
    '''
    This function will enter a record into the logs,
    which will include a message if there is any.

    :param page:
    :param message:
    '''

    # Gets variables needed for the the log entries.
    timestamp = datetime.datetime.utcnow()

    # Override with session details if nothing was supplied.
    if user == None:
        user = session['email']

    # Override with session details if nothing was supplied.
    if account_type == None:
        account_type = session['account_type']

    # Add log entry to the activity_logs collection
    # in the MongoDB database.
    mongo.add_log_entry(timestamp, ip, user, account_type, page, message)

def generate_logs_csv(data):
    '''
    This function will generate a csv for the logs
    to be downloaded by the user. It will return the
    path to the log for download.

    :param results:
    :return output_log_file_path:
    '''

    # Variables used for this function.
    timestamp = (datetime.datetime.utcnow()).strftime("%Y%m%d_%H%M%S%f")
    output_log_file_path = '{}/{}.csv'.format(app.config['LOG_DIRECTORY'], timestamp)

    # Checks if the directory exists. If not, it will
    # create it.
    if not os.path.exists(app.config['LOG_DIRECTORY']):
        os.makedirs(app.config['LOG_DIRECTORY'])

    # Create a log file that contains all the data from
    # the activity logs
    with open(output_log_file_path, "w+", newline="") as log:
        header = "_id,timestamp,source_ip,user,account_type,page,message".split(",")
        csv_writer = csv.DictWriter(log, header, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        csv_writer.writeheader()
        csv_writer.writerows(data)

    # Return the path of the log file.
    return output_log_file_path

def delete_folder_contents(path):
    '''
    This function deletes all the files in a folder,
    specifically looking into the activity logs folder.

    :param path:
    '''

    # Goes through every document in the path
    # and deletes all of the previous log files.
    for document in os.listdir(path):
        # Set up the filename.
        file_path = os.path.join(path, document)

        # Try catch just in case.
        try:
            # If file exists. Delete it.
            if os.path.isfile(file_path):
                os.unlink(file_path)

        except Exception as e:
            print(e)

def regex_check(string):
    '''
    This function will enter a record into the logs,
    which will include a message if there is any.

    :param string:
    :param True/False:
    '''

    # If the regex matches, then we should be good to proceed.
    # Otherwise, if it's no bueno, return false.
    if re.match("^[A-Za-z0-9-]*$", string):
        return True

    else:
        return False


if __name__ == "__main__":
    app.run()
