import datetime
import subprocess
import time

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
# Configuring the blueprint path for Flask to use.
auth_bp = Blueprint('auth', __name__, template_folder='/templates')

# Setting up Login Manager with Flask_Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.refresh_view = 'login'
login_manager.session_protection = 'strong'
login_manager.needs_refresh_message = 'To view protected pages, please re-authenticate.'
login_manager.needs_refresh_message_category = 'info'


#########################################
#          PRE START FUNCTIONS          #
#########################################

@app.before_request
def before_request():
    '''
    This function runs before every request. It
    provides you an extended session of what was
    defined in the config for 'SESSION_TIMEOUT".
    '''

    # Modify the session timeouts in the '__init__'
    # file than hardcoding it here.
    session.permanent = True
    app.permanent_session_lifetime = app.config['SESSION_TIMEOUT']
    session.modified = True


#########################################
#       WEB APPLICATION FUNCTIONS       #
#########################################
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    '''
    This function will process the login functionality
    of the web application. It should return both an
    email and a password, which will then be checked to
    see if the account exists.
    '''

    # This will determine if a session is active, if so,
    # add Flasks' 'current_user' module to add all elements
    # to the session variable.
    if session.get('active') is not None:
        return redirect(url_for('home'))


    # Checks if it's a POST request. If so, process the
    # email and password and see if it exists.
    if request.method == 'POST':
        # Get parameters that were sent by the user.
        email = request.form['input_email']
        password = request.form['input_password']

        # Additional parameters for authenticating and
        # recording the user.
        login_timestamp = datetime.datetime.utcnow()

        # Get user information.
        db_user = mongo.get_one_user_info("email", email)

        # Validate if userexists or not.
        if not db_user:
            # Records log entry.
            main.record_log(request.path,
                            request.remote_addr,
                            'Failed username attempt recorded.',
                            email,
                            "None")

            # Return login template with error message.
            return render_template('/login.html',
                                   type="danger",
                                   value="Username or password is incorrect!")

        # Validates if password matches.
        if not passwd.compare(password, db_user['password']):
            # Records log entry.
            main.record_log(request.path,
                            request.remote_addr,
                            'Failed password attempt recorded.',
                            email,
                            "None")

            # Return login template with error message.
            return render_template('/login.html',
                                   type="danger",
                                   value="Username or password is incorrect!")

        # Create a 'User' object to pass later on.
        user_object = main.User(db_user)

        # Update user's 'last_logon' timestamp.
        result = mongo.update_user_info(db_user['_id'],
                                        'last_logon',
                                        login_timestamp)

        # Login the user.
        login_user(user_object)

        # Redirect to the home page.
        return redirect(url_for('home'))

    # If it's not a POST request, it will most likely be
    # a GET request. Just return the login template.
    else:
        return render_template('/login.html')

@auth_bp.route('/logout', methods=['GET'])
@fresh_login_required
def logout():
    '''
    This is the logout function. It clears all the
    session information about the user and it will
    also log the user out. Once that's done, it should
    redirect the user to the homepage, which should
    then redirect back to the login page.
    '''

    # Records log entry.
    main.record_log(request.path,
                    request.remote_addr,
                    'User successfully logged out.')

    # Clears session information and logs the user out.
    session.clear()
    logout_user()

    # Upon logging out, redirects user to the home page.
    return redirect(url_for('home'))

@auth_bp.route('/register', methods=['GET', 'POST'])
@fresh_login_required
def register():
    '''
    This function will register a new user into the
    users collection for the MongoDB database.
    '''
    # Checks if the user is an admin to show this
    # page or not.
    if session['account_type'] == 'admin':

        # Checks if it's a POST request. If so, process the
        # input information to create the user.
        if request.method == 'POST':
            # Creating a user "object" to send over to the
            # MongoDB API to add user.
            user = dict()

            # Get parameters that were sent by the user.
            user['first_name'] = request.form['input_first_name']
            user['last_name'] = request.form['input_last_name']
            user['email'] = request.form['input_email']
            user['password'] = request.form['input_password']
            user['password_repeat'] = request.form['input_password_repeat']
            user['account_type'] = request.form['input_account_type']
            user['avatar'] = request.form['input_avatar']
            user['theme_color'] = "primary"
            user['active'] = True

            # Get user information.
            db_user = mongo.get_one_user_info("email", user['email'])

            # Validate if userexists or not.
            if db_user is not None:
                # Return register template with error message.
                message = "User {} already exists! Try a different one.".format(user['email'])
                return render_template('/register.html',
                                    title="Register",
                                    type="danger",
                                    value=message,
                                    user=session)

            # Validates if passwords match
            if user['password'] != user['password_repeat']:
                # Return register template with error message.
                return render_template('/register.html', 
                                    title="Register",
                                    type="danger",
                                    value="Passwords do not match! Try again.",
                                    user=session)

            # Validates if first name contains only letters, numbers
            # and/or hyphens
            if not main.regex_check(user['first_name']) or not main.regex_check(user['last_name']):
                # Return register template with error message.
                return render_template('/register.html', 
                                    title="Register",
                                    type="danger",
                                    value="Names can only include letters, numbers and/or hyphens. Try again.",
                                    user=session)

            # Calculate Hashed password and delete plaintext password
            user['hashed_password'] = (passwd.hash(user['password'])).decode()

            del user['password_repeat']

            # Additional parameters for authenticating and
            # recording the user.
            user['registration_date'] = datetime.datetime.utcnow()
            user['last_password_change'] = datetime.datetime.utcnow()
            user['last_logon'] = ''
            user['uuid'] = mongo.get_largest_uuid() + 1

            # Create SFTP account for the user.
            create_sftp(user['email'], user['password'])

            # Replace password with hashed password and delete it.
            user['password'] = user['hashed_password']
            del user['hashed_password']

            # Add user to the MongoDB database 'users' collection.
            mongo.add_user(user)

            # Blank the password out.
            del user['password']

            # Records log entry.
            message = 'Created the user {}.'.format(user['email'])
            main.record_log(request.path,
                            request.remote_addr,
                            message)

            # Return template with user created
            return render_template('/register.html',
                            title="Register",
                            type="success",
                            value=message,
                            user=session)

        # Records log entry.
        main.record_log(request.path,
                        request.remote_addr,
                        'Viewed the Register page.')

        return render_template('/register.html',
                            title="Register",
                            user=session)
        
    else:
        # Records log entry.
        main.record_log(request.path,
                        request.remote_addr,
                        'User attempted to access the Register User page. Forbidden.')
        
        # Redirect to home page.
        return redirect(url_for('home'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@fresh_login_required
def profile():
    '''
    This is the profile page. This will be all of the items
    associated to the profile of the user account at question.
    '''

    if request.method == 'POST':
        # Creating a user "object" to send over to the
        # MongoDB API to add user.
        user = dict()
        change_list = list()
        time_now = datetime.datetime.utcnow()

        # Get parameters that were sent by the user.
        user['first_name'] = request.form['input_first_name']
        user['last_name'] = request.form['input_last_name']
        user['email'] = request.form['input_email']
        user['old_password'] = request.form['input_old_password']
        user['new_password'] = request.form['input_new_password']
        user['avatar'] = request.form['input_avatar']
        user['theme_color'] = request.form['input_theme_color']

        if user['email'] != session['email']:
            return render_template('/profile.html', 
                                   title="Profile",
                                   type="danger",
                                   value="Even though it allows you to change emails. I just won't let you :)",
                                   user=session)

        # Get user information.
        db_user = mongo.get_one_user_info("email", user['email'])

        # Valid password is required to make changes. Here
        # we check the hash of the user's password:
        results = passwd.compare(user['old_password'], db_user['password'])

        # If password does not match, return error.
        if results == False:
            return render_template('/profile.html', 
                                   title="Profile",
                                   type="danger",
                                   value="Incorrect password. Try again.",
                                   user=session)

        # Validates if first name contains only letters, numbers
        # and/or hyphens
        if not main.regex_check(user['first_name']) or not main.regex_check(user['last_name']):
            # Return register template with error message.
            return render_template('/profile.html', 
                                   title="Profile",
                                   type="danger",
                                   value="Names can only include letters, numbers and/or hyphens. Try again.",
                                   user=session)

        # Calculate Hashed password and delete plaintext password.
        # Update the password and record log entry.
        if user['new_password'] != "":
            user['hashed_password'] = passwd.hash(user['new_password'])

            # Change session variable information
            session['last_password_change'] = time_now

            # Update the user data in the MongoDB with the accurate time.
            mongo.update_user_info(db_user['_id'], 'last_password_change', time_now)
            mongo.update_user_info(db_user['_id'], 'password', user['hashed_password'].decode())

            # Create SFTP account for the user.
            create_sftp(user['email'], user['new_password'])

            # Blank the password out.
            del user['new_password']
            
            # Record log entry
            main.record_log(request.path,
                            request.remote_addr,
                            'User has updated their password.')

        # Change all the values that need to be changed and
        # append the results into a list so that we can check
        # if there has been any change whatsoever. If so, record
        # it in the logs.
        change_list.append(check_if_same_data(db_user['_id'],
                                              'first_name',
                                              user['first_name'],
                                              db_user['first_name']))

        change_list.append(check_if_same_data(db_user['_id'],
                                              'last_name',
                                              user['last_name'],
                                              db_user['last_name']))

        change_list.append(check_if_same_data(db_user['_id'],
                                              'avatar',
                                              user['avatar'],
                                              db_user['avatar']))

        change_list.append(check_if_same_data(db_user['_id'],
                                              'theme_color',
                                              user['theme_color'],
                                              db_user['theme_color']))

        change_list.append(check_if_same_data(db_user['_id'],
                                              'last_name',
                                              user['last_name'],
                                              db_user['last_name']))

        if False in change_list:
            main.record_log(request.path,
                            request.remote_addr,
                            'User has updated their account information.')
        
        # Update the session information
        session['first_name'] = user['first_name']
        session['last_name'] = user['last_name']
        session['avatar'] = user['avatar']
        session['theme_color'] = user['theme_color']

    # Records log entry.
    main.record_log(request.path,
                    request.remote_addr,
                    'Viewed the Profile page.')

    return render_template('/profile.html',
                           title='Profile',
                           user=session)

@auth_bp.route('/users', methods=['GET'])
@fresh_login_required
def manage_users():
    '''
    This function will register a new user into the
    users collection for the MongoDB database.
    '''
    # Checks if the user is an admin to show this
    # page or not.
    if session['account_type'] == 'admin':

        # Records log entry.
        main.record_log(request.path,
                        request.remote_addr,
                        'Viewed the Manage Users page.')

        return render_template('/users.html',
                            title="Manage Users",
                            user=session)
        
    else:
        # Records log entry.
        main.record_log(request.path,
                        request.remote_addr,
                        'User attempted to access the Manage Users page. Forbidden.')
        
        # Redirect to home page.
        return redirect(url_for('home'))

#########################################
#            OTHER FUNCTIONS            #
#########################################
def check_if_same_data(_id, data_type, new, existing):
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
        mongo.update_user_info(_id, data_type, new)
        return False
    
    else:
        return True

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

# def create_token(email, user_id, timestamp):
#     '''
#     This function will generate a custom token using an
#     email, id and the current timestamp.

#     :param email:
#     :param id:
#     :param timestamp:

#     :return: token
#     '''

#     # Calculate a non-datetime timestamp, solely a string.
#     clean_timestamp = timestamp.strftime("%Y%m%d%H%M%S%f")

#     # Calculate Step One which is the base 64 encoded results.
#     step_one = (email+str(user_id)).encode()
#     step_one_processed = passwd.pre_process_input(step_one)

#     # Calculate Step two which is the base 64 encoded results,
#     # and return that data.
#     step_two = (clean_timestamp.encode()+step_one_processed)
#     token = (passwd.pre_process_input(step_two)).decode()

#     # Record this entry into the database to ensure that tokens
#     # do not get reused.
#     mongo.add_token(email, user_id, timestamp, clean_timestamp, token)


#     return token