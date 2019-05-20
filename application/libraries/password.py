import base64
import bcrypt
import hashlib

'''
This script will contain all the functions required to process
passwords and hashes across the application. 
'''

def compare(plaintext, password_hash):
    '''
    This function will check the plaintext password provided by
    the user with the hashed bcrypt password ideally obtained from
    the database.

    :param plaintext:
    :param password_hash:
    :return True or False:
    '''

    # Hashes the plaintext password provided by the user given the
    # max number of characters that bcrypt can use (72).
    processed_value = pre_process_input(plaintext.encode())

    # Returns a True if the password does match, or a False if the
    # password does not match.
    return bcrypt.checkpw(processed_value, password_hash.encode())

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