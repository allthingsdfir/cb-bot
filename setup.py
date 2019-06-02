import base64
import datetime
import getpass
import hashlib
import os
import random
import subprocess
import time

import bcrypt
import pymongo

# Create data folder before starting MongoDB
os.makedirs('{}/data'.format(os.getcwd()), exist_ok=True)

# Starts up a MongoDB child process.
# Runs a subprocess. If you can tee it, great. but
# having the open function will output the log nicely.
# mongod --dbpath data/ --port 5051 | tee mongo.log
with open('{}/mongo.log'.format(os.getcwd()),"wb") as out:
    process = subprocess.Popen(['mongod',
                                '--dbpath',
                                'data/',
                                '--port',
                                '5051'],
                                shell=False,
                                stdout=out,
                                stderr=out)

#################################
#     Create 'doby' database    #
#################################
print("[*]\n[*] Creating 'doby' database...")

client = pymongo.MongoClient('127.0.0.1', 5051)
db = client.doby

print("[*] Database 'doby' created!")

def apply_generic_server_settings():
    '''
    Creating all of the basic server settings used in this
    unique Doby instance.
    '''
    
    print("[*] ------------------------")
    print("[*] Adding generic Doby server configs...")

    print("[*]\n[*] Let's start by naming/numbering your case.")
    case_name = str(validate_user_input('Case Number/Name (e.g. CASE19-001, PWN_CLIENT')).lower()
    
    case_settings = {
        "name" : "Doby",
        "case" : case_name
    }

    print("[*]\n[*] Added Case Number/Name!")

    # Define Giphy settings
    giphy_settings = {
        "name" : "Giphy",
        "root_url" : "https://api.giphy.com/v1/gifs/random",
        "api_key" : "VJdvL7tDGhzqg4GnNYLBOLtoyHnxBtSA",
        "rating" : "PG-13"
    }

    print("[*]\n[*] Added Giphy config!")

    # Define simple CB settings. Mostly placeholders.
    cb_server_settings = {
        "name" : "Carbon Black",
        "root_url" : "",
        "api_key" : "",
        "connector_id" : "",
        "max_sessions" : "30",
        "min_check_in_time" : "3"
    }

    print("[*]\n[*] Added Carbon Black (CB) config! Please make")
    print("[*] sure to change it once authenticated and")
    print("[*] you have the CB data you need.")

    # Adds the newly created server settings/config.
    db.settings.insert_one(giphy_settings)
    db.settings.insert_one(cb_server_settings)
    db.settings.insert_one(case_settings)

def create_admin_account():
    '''
    Creating an admin account for the initial usage of Doby.
    The user can select any username for this method. If the
    script is re-run, it will still create another user. So,
    beware.
    '''

    # Variable definition. Initizalizing all of the variables
    # used in this function.
    user = dict()

    # User values requiring user input.
    user['email'] = str()
    user['password'] = str()
    user['first_name'] = str()
    user['last_name'] = str()

    # Pre-defined falues.
    user['avatar'] = str('avatar_{}'.format(random.randint(1,10)))
    user['theme_color'] = str('primary')
    user['active'] = True
    user['uuid'] = get_largest_uuid() + 1
    user['account_type'] = 'admin'
    
    # Printing message indicating the creation of a user account.
    print('[*] ------------------------')
    print('[*] Let\'s set up an admin account for Doby.')

    # Get and validate user input.
    user['email'] = str(validate_user_input('Email')).lower()
    user['first_name'] = str(validate_user_input('First Name')).title()
    user['last_name'] = str(validate_user_input('Last Name')).title()

    # Reset the flag to false.
    flag = False

    # While flag is looking for correct user
    # input: password
    while flag == False:

        # Collect user input for password.
        password = getpass.getpass(prompt='[*]\n[*] Please type in a Password: ', stream=None) 
        retype_password = getpass.getpass(prompt='[*] Please re-type in a Password: ', stream=None) 
        
        # Check if password are the same.
        if password == retype_password:
            del retype_password
            user['password'] = hash(password)
            flag = True

        # If password is not the same, keep trying. Reset variables.
        else:
            password = ''
            retype_password = ''
            print('[*] Passwords don\'t match! Please try again.')
    
    # Calculate time account was created.
    user['registration_date'] = datetime.datetime.utcnow()
    user['last_password_change'] = datetime.datetime.utcnow()

    # Create SFTP account for the user.
    create_sftp(user['email'], password)

    # Blank the password out.
    password = ''

    # Adds the newly created user to the mongo database.
    db.users.insert_one(user)

    # Print message or user added.
    print("[*]\n[*] ------------------------")
    print("[*]\n[*] Adding generic Doby server configs...")

def create_base_folders():
    '''
    Creates all of the base folders needed for
    Doby to run.
    '''

    # Get current working directory
    cwd = os.getcwd()

    # Create folders
    os.makedirs('{}/data'.format(cwd), exist_ok=True)
    os.makedirs('/data/sweep_output', exist_ok=True)
    os.makedirs('{}/temp'.format(cwd), exist_ok=True)
    os.makedirs('{}/temp/logs'.format(cwd), exist_ok=True)

def create_sftp(email, password):
    '''
    Creates an SFTP account for the admin user.
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
    proc.stdin.flush()

def create_collections():
    '''
    Creates MongoDB collections for Doby CB. Even if the collection
    exists, it will not overwrite it at all. We use this function to
    ensure that at least they have been instanciated and do not need
    to worry about creating it while Doby is running in production.
    '''
    
    # Printing information about collections.
    print("[*] ------------------------")
    print("[*] Creating collections in 'doby' database...")

    collection_list = ['activity_logs', 'alerts', 'cb_hosts', 'server_settings', 'sweep_commands', 'sweep_log', 'task_history', 'users']

    # Creatie all of the collections.
    for collection in collection_list:
        # Checks to see if the collection exists already or not.
        try:
            db.create_collection(collection)
            print("[*]     |-> Creating '{}' collection...".format(collection))
        except:
            # Most likely the collection exists. Skip.
            print("[*]     |-> Collection '{}' exists... Skipping".format(collection))
            pass

    # Printing information about completed collections.
    print("[*] {} default collections created!".format(len(collection_list)))

def get_largest_uuid():
    '''
    Gets the largest UUID for the users in the database.
    
    :return uuid:
    '''

    # Queries the MongoDB database for the largest UUID
    user_list = list(db.users.find({}).sort('uuid', pymongo.DESCENDING))

    # Checks if there are no UUIDs. If none, return 0.
    if len(user_list) == 0:
        return 0

    return user_list[0]['uuid']

def hash(password_input):
    '''
    This function will hash and salt a password provided by the
    user. It will generate a random salt per instance that the
    function runs.

    :param password_input:
    :return hashed_password:
    '''

    # Hashes the plaintext password provided by the user given the
    # max number of characters that bcrypt can use (72).
    processed_value = pre_process_input(password_input.encode())

    # Utilize bcrypt to hash "processed_value" using a randomly generated
    # salt for each password generated.
    hashed_password = bcrypt.hashpw(processed_value, bcrypt.gensalt())

    # Returns the hashed_password to be stored.
    return hashed_password

def pre_process_input(plaintext):
    '''
    Hashes the plaintext password due to the maximum bcrypt algorithm
    that limits the length of passwords to 72 characters. Hashing the
    input would get a unique hash that can be then used to get a hashed
    value of the hashed password or to compare that against the pass-
    word stored in the database.

    :param plaintext:
    :return processed_value:
    '''

    # Since bcrypt has a maximum of 72 characters for password,
    # "processed_value" is the hashed base 64 encoded value of the
    # password supplied. Therefore, regardless of password length,
    # it will collect the hash and then hash that password.
    processed_value = hashlib.sha256(plaintext).digest()
    processed_value = base64.b64encode(processed_value)

    # Returns the base64 encoded results from the hashed plaintext
    # password.
    return processed_value

def validate_user_input(text_value):
    '''
    Flag to validate user input is correct
    before moving to the creation of the
    user account.
    '''

    # Variables used to validate user input
    correct = ['y', 'yes', 'yea', 'yeah', 'positive', 'true']
    incorrect = ['n', 'no', 'not', 'nah', 'negative', 'false']

    # While flag is looking for correct user input
    # so that it can confirm the condition.
    while True:

        # Collect user input for username
        value = str(input('[*]\n[*] Please type in your {}: '.format(text_value)))
        accept_flag = str(input('[*] Is \'{}\' correct (Yes) or (No): '.format(value)))
        
        # Verify what the response is from the user.
        # If the data is correct, the user most likely,
        # will respond with a 'correct' value, thus
        # exiting the code. Otherwise, it will continously
        # run until the user acknowledges the input data
        # is correct.
        if accept_flag in correct:
            return value

        # False/Negative/Incorrect flag.
        elif accept_flag in incorrect:
            pass
        
        # Weird strings selected will indicate what are
        # the only things that can be used.
        else:
            print('[*]\n[*] Please use only the accepted inputs:')
            print('[*]    y, yes, yea, yeah, positive, true')
            print('[*]    n, no, not, nah, negative, false')

def main():
    '''
    Main function for the Doby initializator.
    '''

    create_base_folders()
    create_collections()
    create_admin_account()
    apply_generic_server_settings()

if __name__ == "__main__":
    main()
