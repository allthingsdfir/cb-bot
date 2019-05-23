import pymongo
import datetime
import time
import getpass
import hashlib
import base64
import bcrypt
import random

#################################
#     Create 'doby' database    #
#################################
print("[*]\n[*] Creating 'doby' database...")
print("[*] Creating 'doby' database...")

client = pymongo.MongoClient('127.0.0.1', 5051)
db = client.doby

print("[*] Database 'doby' created!")

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

    # Creatie all of the collections.
    db.create_collection('activity_logs')
    print("[*]     |-> Creating 'activity_logs' collection...")
    db.create_collection('alerts')
    print("[*]     |-> Creating 'alerts' collection...")
    db.create_collection('cb_hosts')
    print("[*]     |-> Creating 'cb_hosts' collection...")
    db.create_collection('server_settings')
    print("[*]     |-> Creating 'server_settings' collection...")
    db.create_collection('sweep_commands')
    print("[*]     |-> Creating 'sweep_commands' collection...")
    db.create_collection('sweep_log')
    print("[*]     |-> Creating 'sweep_log' collection...")
    db.create_collection('task_history')
    print("[*]     |-> Creating 'task_history' collection...")
    db.create_collection('users')
    print("[*]     |-> Creating 'users' collection...")

    # Printing information about completed collections.
    print("[*] Eight (8) default collections created!")

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

    # Adds the newly created user to the mongo database.
    db.users.insert_one(user)

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

def apply_generic_server_settings():
    #################################
    #       Add server settings     #
    #################################
    print("[*] ------------------------")
    print("[*] Adding generic Doby server configs...")

    giphy_settings = {
        "name" : "Giphy",
        "root_url" : "https://api.giphy.com/v1/gifs/random",
        "api_key" : "VJdvL7tDGhzqg4GnNYLBOLtoyHnxBtSA",
        "rating" : "PG-13"
    }

    print("[*]\n[*] Added Gihpy config!")

    cb_server_settings = {
        "name" : "Carbon Black",
        "root_url" : "",
        "api_key" : "",
        "connector_id" : "",
        "max_sessions" : "30",
        "min_check_in_time" : "3"
    }

    print("[*]\n[*] Added Carbon Black (CB) config! Please make")
    print("[*]\n[*] sure to change it once authenticated and")
    print("[*]\n[*] you have the CB data you need.")

    # Adds the newly created server settings/config.
    db.settings.insert_one(giphy_settings)
    db.settings.insert_one(cb_server_settings)

def main():
    '''
    Main function for the Doby initializator.
    '''

    # create_collections()
    # create_admin_account()
    apply_generic_server_settings()

if __name__ == "__main__":
    main()





# # Sets the players table with the current users all defaulted to same ranking
# roster = db.players
# player_list = []

# userDict = {
#     'Chan': '69168231213',
#     'Tomczak': '1421313216',
#     'Westfall': '1421913216'
# }

# for name, badge_id in userDict.iteritems():

#     while len(badge_id) < 12:
#         badge_id = "0" + badge_id

#     users = {}
#     users['name'] = name
#     users['badge_id'] = int(badge_id)
#     users['company'] = "Foos Fighters LLC"
#     users['points'] = 1000
#     users['wins'] = 0
#     users['losses'] = 0
#     users['goals_scored'] = 0
#     users['goals_against'] = 0
#     users['enroll_date'] = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
#     users['temporary'] = False
#     player_list.append(users.copy())

# # Temporary badges.
# # tempDict = {
# #     'TEMP_BLUE': '182723518',
# #     'TEMP_RED': '10123113793'
# # }

# # for name, badge_id in tempDict.iteritems():

# #     while len(badge_id) < 12:
# #         badge_id = "0" + badge_id

# #     users = {}
# #     users['name'] = name
# #     users['badge_id'] = badge_id
# #     users['points'] = 1000
# #     users['wins'] = 0
# #     users['losses'] = 0
# #     users['goals_scored'] = 0
# #     users['goals_against'] = 0
# #     users['enroll_date'] = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
# #     users['temporary'] = True
# #     player_list.append(users.copy())

# print "[*] %s players being added." % len(player_list)

# time.sleep(1)
# players_record_id = roster.insert(player_list)

# print "[*] Players migrated to 'players' table!"
# print "[*] ---"

# # # Sets the trolls table with the current trolls.
# # troll_db = db.trolls

# # troll_list = []

# # generic = [
# #     "Umm, did <user> just leave a mobile happy hour because they just played like they're hammered (facepalm)", 
# #     "Will somebody request an Uber to take <user> home? They will likely still be in the fetal position by EOD.", 
# #     "<user>, you never had me - you never had your car!", 
# #     "<user>, your ability to select a suitable opponent exceeds that of CrowdStrike's ability to acquire files.", 
# #     "Clearly becoming better at foos is not one of your MBOs, <user>.", 
# #     "<user>, I think chess may be more of your sport.", 
# #     "Adding <user> to known bad.", 
# #     "You may have lost, <user>, but at least you also lost chargeable time & IC.", 
# #     "I think you need to pay back some sparks after that loss, <user>.", 
# #     "<user>, this loss has been recorded to your record and will used to evaluate your promotion/demotion eligibility.", 
# #     "Looks like the surricata service has died on <user>.", 
# #     "Directing all 'How do I host lookup on mstack' questions to <user>.", 
# #     "<user> is reverting to their last known good snapshot.", 
# #     "<user>, do you even foos?", 
# #     "<user>, I heard that CrowdStrike is having foosball tryouts that may be more your level.", 
# #     "Some things in life it's acceptable to fail at. Foos is NOT one of those things.", 
# #     "<user>, maybe you should sign up for lessons?",
# #     "But <user>, your resume said you were good at foos...",
# #     "Let's see how low can <user>'s rating go: http://www.gifbin.com/bin/082012/1346779156_extremely_low_limbo.gif",
# #     "looks like you need more coffee."
# # ]

# # playerTroll = {
# #     'Tomczak': [
# #         "Tomczak, too bad you lost after all of those spin shots. Would you mind repositioning the foos table to its proper location?",
# #         "Tomczak, you should rewrite your game in GO so it's better.",
# #         "TZWorks. Spinning doesn't.",
# #         "You must have buns of steel because you seem to partake in many a spin class. #spinningaintwinning",
# #         "Less wrist and more accuracy, maybe?",
# #         "Hey Tomczak, I heard your dog plays better than that.",
# #         "It's okay Tomczak, you still have the Godliest shot in the league!",
# #         "Tomczak, is that how they play in Maryland?", 
# #         "Are we at your home? Because you just got schooled!"
# #     ]
# # }

# # for gen_troll in generic:
# #     troll = {}
# #     troll['name'] = 'Generic'
# #     troll['troll'] = gen_troll
# #     troll_list.append(troll.copy())

# # for name, trolls in playerTroll.iteritems():
# #     troll = {}
# #     for spec_troll in trolls:
# #         troll['name'] = name
# #         troll['troll'] = spec_troll
# #         troll_list.append(troll.copy())

# # print "[*] %s trolls being added." % len(troll_list)

# # time.sleep(1)
# # trolls_record_id = troll_db.insert(troll_list)

# # print "[*] Trolls migrated to 'trolls' table!"
# print "[*] ---"
# print "[*] Listing all current tables in 'foosball' database:"

# time.sleep(1)

# for tables in list(db.collection_names()):
#     print "[*]  '%s' table identified" % tables

# print "[*] ---"
# print "[*] Migration complete!"