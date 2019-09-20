import datetime
import json
import os
import queue
import sys
import threading
import time

import pymongo
import requests

requests.packages.urllib3.disable_warnings()

# Database configuration
MONGO_CLIENT = pymongo.MongoClient('127.0.0.1', 5051)
CB_BOT_DB = MONGO_CLIENT.cb_bot

# Get configuration from the MongoDB. There should only be
# one item or none. Potential implementation of multiple
# CB Server Configuration is possible, just not implemented yet.
list_data = list(CB_BOT_DB.server_settings.find({"name": "Carbon Black"}))

# Determines if there is data to be sent back. If there
# are no configurations set, then it should return blank.
if len(list_data) > 0:
    config = list_data[0]

else:
    print("[*] No config file provided.")
    quit()

# Output folder path.
OUTPUT_DIRECTORY = sys.argv[1]

# Define Carbon Black instance settings.
CB_ROOT_URL = config['root_url']
CB_API_KEY = config['api_key']
CB_CONNECTOR_ID = config['connector_id']
CB_XAUTH_TOKEN = '{}/{}'.format(CB_API_KEY, CB_CONNECTOR_ID)
CB_CONCURRENT_SESSIONS = int(config['max_sessions'])
CB_MIN_CHECK_IN_TIME = int(config['min_check_in_time'])

# This gets the task id and the command id.
TUID = int(sys.argv[2])
CUID = int(CB_BOT_DB.task_history.find_one({'tuid': int(TUID)})['cuid'])

# Input value is optional. If set to false, then
# there is no input file.
try:
    INPUT_FILE = str(sys.argv[3])
except:
    INPUT_FILE = False

# Input value is optional. If set to false, then
# there is no input file.
try:
    COMMAND_TO_EXECUTE = str(sys.argv[4])
except:
    COMMAND_TO_EXECUTE = False

# Get error count for all of the data collection. 
# If self.ERROR_COUNT reaches the threshold, it will
# stop the queue.
ERROR_COUNT = 0
ERROR_THRESHOLD = 100

# This is the API waiting period in seconds and the
# sleep period between calls.
WAITING_PERIOD = 200
SLEEP_INTERVAL = 5


class CB_BOT():

    def __init__(self, queue_list, total_hosts, command_specs, _id, sweep_name):
        self.queue_list = queue_list
        self.total_hosts = total_hosts
        self.task_object_id = _id
        self.sweep_name = sweep_name
        self.command_type = command_specs['command_type']

        self.ERROR_COUNT = ERROR_COUNT
        self.ERROR_THRESHOLD = ERROR_THRESHOLD
        self.WAITING_PERIOD = WAITING_PERIOD
        self.SLEEP_INTERVAL = SLEEP_INTERVAL

        self.CB_ROOT_URL = CB_ROOT_URL
        self.CB_XAUTH_TOKEN = CB_XAUTH_TOKEN
        self.CB_CONCURRENT_SESSIONS = CB_CONCURRENT_SESSIONS
        self.CB_MIN_CHECK_IN_TIME = CB_MIN_CHECK_IN_TIME

        self.TUID = TUID

        # Checks to see if there was an input file for the user. If so,
        # add it to the commmand for execution on the endpoint.
        if self.command_type == 3:
            self.out_file = INPUT_FILE
            self.command = command_specs['command']
            # We have to ensure if we need to insert another command or not.
            # self.command = self.command.replace('{||}', out_file)
            
        # This is another validator looking for the file to
        # upload to CB.
        elif self.command_type == 2:
            self.upload_file = INPUT_FILE
            self.command = COMMAND_TO_EXECUTE

        else:
            self.command = command_specs['command']
            self.out_file = command_specs['output_file']

    def run_sweep(self):
        '''
        Gets a worker to run the designated sweep. The function
        essentially does the following:

            - Open CB Session.
                + Check CB Session is Active.
            - Run Command using CB Session.
                + Check Command using CB Session to see if Completed.
            - Get Created File using CB Session.
            - Delete Created File using CB Session.
            - End CB Session.

        '''

        # Ensures that there are no more elements in the Queue to be taking
        while queue.Queue.qsize(self.queue_list) != 0:
            # This checks if the error count has met the threshold
            # in order to prevent from continuous crap out.
            if self.ERROR_COUNT > self.ERROR_THRESHOLD:
                # Updates the task ID to false. Indicating that there
                # was an issue and needs to end.

                # Checks if there are more threads running before
                # setting this to false.
                # ========= DEV =========
                print("Active threads: {}".format(threading.active_count()))
                # ========= DEV =========

                if threading.active_count() == 1:
                    # Create an alert.
                    alert = dict()
                    auid = get_largest_auid() + 1
                    timestamp = datetime.datetime.utcnow()
                    alert['created'] = timestamp
                    alert['message_date'] = timestamp.strftime("%B %d, %Y  %-I:%M %p UTC")
                    alert['active'] = True
                    alert['owner'] = get_task_owner()
                    alert['auid'] = auid
                    alert['message'] = "Failed Sweep with Task ID {}: {}. cb_bot workers errored out.".format(self.TUID, self.sweep_name)

                    # Tell Mongo to add alert.
                    create_alert(alert)

                    # Updated the task.
                    update_task('active', False, self.task_object_id)

                # Kills the thread and ultimately the sweep.
                quit()

            try:
                # Collects an available queue object
                queue_obj = self.queue_list.get(timeout=1)
                
                # Define the sensor name and the id based
                # on the queue object obtained.
                sensor_name = queue_obj.split('||')[0]
                sensor_id = queue_obj.split('||')[1]

                # Host Mongo DB object ID
                host_object_id = self.get_sweep_log_host_id(sensor_id)

                # We need to check the time of the sensor's last
                # reported timestamp. If falls within the scope,
                # work on it.
                host_last_reported = self.get_host_last_reported_time(sensor_id)

                # Check if no timestamp was recorded
                if host_last_reported != False:
                    # Continue since there is a host_last_reported
                    time_elapsed = datetime.datetime.utcnow() - host_last_reported
                    duration = time_elapsed.total_seconds()
                    total_diff = int(divmod(duration, 3600)[0])

                    # Validate if time is greater than the self.CB_MIN_CHECK_IN_TIME
                    # before proceeding. if it is greater, just break and re-add
                    # the host back to the list.
                    if total_diff <= self.CB_MIN_CHECK_IN_TIME:

                        # # ========= DEV =========
                        # print("Active threads: {}".format(threading.active_count()))
                        # print("Queue size: {}".format(queue.Queue.qsize(self.queue_list)))
                        # print("Working on host: {} | {}".format(sensor_name, sensor_id))
                        # # ========= DEV =========

                        print("[TASK ID: {}] Active threads: {}".format(self.TUID, threading.active_count()))
                        print("[TASK ID: {}] Queue Size: {}".format(self.TUID, queue.Queue.qsize(self.queue_list)))

                        ###########################
                        # Step 1: Open CB Session #
                        ###########################

                        # Attempts to get a LR session.
                        session_id = self.session_open(sensor_id, sensor_name)

                        # Check if response was valid. -1 indicates that
                        # nothing was sent back. Adds the sensor_id to the list
                        # of unfinished ones.
                        if session_id != -1:
                            ############################################
                            # Step 2: Check Command Type And Run Sweep #
                            ############################################

                            # Depending on the type of sweep, we need to
                            # perform different sets of actions. So here,
                            # we check for the command type, and follow
                            # the set of actions we need per job.
                            
                            # ==== Type 1: Run command and get file output. ====
                            if self.command_type == 1:
                                # Execute the command that we want it to do.
                                command_status = self.command_execute(session_id, sensor_name)

                                if command_status == True:
                                    # Goes to collect the file.
                                    file_results = self.get_file_request(session_id, sensor_name)

                                    # This is if the file collection was complete.
                                    if file_results == True:
                                        # Update the host in the sweep log.
                                        self.update_one_host_sweep('status', 'Results collected!', host_object_id)
                                        self.update_one_host_sweep('complete', True, host_object_id)
                                        self.update_one_host_sweep('completed_timestamp', datetime.datetime.utcnow(), host_object_id)

                                    else:
                                        # We were not able to get a file, there was an error.
                                        self.update_one_host_sweep('status', 'Command ran, but was unable to collect results.', host_object_id)
                                        self.queue_list.task_done()
                                        self.queue_list.put('{}||{}'.format(sensor_name, sensor_id))

                                    # Delete file on disk.
                                    results = self.delete_file(session_id, sensor_name, self.out_file)

                                    # Store updated list in Mongo.
                                    self.update_completed_hosts_task()

                                else:
                                    # We were not able to run a command.
                                    self.update_one_host_sweep('status', 'Could not run command on the host.', host_object_id)
                                    self.queue_list.task_done()
                                    self.queue_list.put('{}||{}'.format(sensor_name, sensor_id))


                            # ==== Type 2: Upload file and run. ====
                            elif self.command_type == 2:
                                

                                # Send request to upload file.
                                upload_status = self.upload_file_to_cb(session_id, sensor_name)

                                # If upload worked, execute it.
                                if upload_status == True:
                                    # Execute the command that we want it to do.
                                    command_status = self.command_execute(session_id, sensor_name)

                                    if command_status == True:
                                        # We were not able to get a file, there was an error.
                                        self.update_one_host_sweep('status', 'Success. File uploaded and command executed.', host_object_id)
                                        self.update_one_host_sweep('complete', True, host_object_id)
                                        self.update_one_host_sweep('completed_timestamp', datetime.datetime.utcnow(), host_object_id)

                                        # Delete file on disk.
                                        results = self.delete_file(session_id, sensor_name, self.upload_file)

                                        # Store updated list in Mongo.
                                        self.update_completed_hosts_task()

                                    else:
                                        # We were not able to run a command.
                                        self.update_one_host_sweep('status', 'Could not run command on the host.', host_object_id)
                                        self.queue_list.task_done()
                                        self.queue_list.put('{}||{}'.format(sensor_name, sensor_id))

                                # Re-add to queue and update host status.
                                else:
                                    # We were not able to upload file.
                                    self.update_one_host_sweep('status', 'Error uploading file to the system.', host_object_id)
                                    self.queue_list.task_done()
                                    self.queue_list.put('{}||{}'.format(sensor_name, sensor_id))

                            # ==== Type 3: Get file from system. ====
                            elif self.command_type == 3:
                                
                                # Goes to collect the file.
                                file_results = self.get_file_request(session_id, sensor_name)

                                # This is if the file collection was complete.
                                if file_results == True:
                                    # Update the host in the sweep log.
                                    self.update_one_host_sweep('status', 'Results collected!', host_object_id)
                                    self.update_one_host_sweep('complete', True, host_object_id)
                                    self.update_one_host_sweep('completed_timestamp', datetime.datetime.utcnow(), host_object_id)

                                else:
                                    # We were not able to get a file, there was an error.
                                    self.update_one_host_sweep('status', 'Unable to collect file!', host_object_id)
                                    self.queue_list.task_done()
                                    self.queue_list.put('{}||{}'.format(sensor_name, sensor_id))

                                # Delete file on disk.
                                results = self.delete_file(session_id, sensor_name, self.out_file)

                                # Store updated list in Mongo.
                                self.update_completed_hosts_task()

                            else:
                                print("COMMAND DOES NOT EXIST! NEED TO ADD ACTION.")

                            ##################################################
                            # Step 3: Close Session & Remove Host From Queue #
                            ##################################################

                            # Close session without caring what command type it is
                            # or if the commands successfully ran or not.
                            self.session_close(session_id, sensor_name)
                            self.queue_list.task_done()

                        else:
                            self.update_one_host_sweep('status', 'Could not establish a CB session.', host_object_id)
                            self.queue_list.task_done()
                            self.queue_list.put('{}||{}'.format(sensor_name, sensor_id))

                    else:
                        self.update_one_host_sweep('status', 'Host falls outside of minimum check in time.', host_object_id)
                        self.queue_list.task_done()
                        self.queue_list.put('{}||{}'.format(sensor_name, sensor_id))

                else:
                    self.update_one_host_sweep('status', 'No last reported timestamp recorded.', host_object_id)
                    self.queue_list.task_done()
                    self.queue_list.put('{}||{}'.format(sensor_name, sensor_id))

            except Exception as e:
                self.ERROR_COUNT += 1
                self.queue_list.task_done()
                self.queue_list.put('{}||{}'.format(sensor_name, sensor_id))

                # ========= DEV =========
                print("Some error ocurred. Count is at: {}".format(self.ERROR_COUNT))
                print(e)
                # ========= DEV =========

    def session_check(self, session_id, sensor_name):
        '''
        This checks a session. We will try for 5 minutes,
        or whichever self.WAITING_PERIOD is set to in seconds.
        If no session comes up, we will add to unifinished
        hosts and move on with the queue.
        '''
        count = 0 

        # This is to try a request every 2 seconds.
        while count < self.WAITING_PERIOD:
            # Sleep for self.SLEEP_INTERVAL in seconds
            time.sleep(self.SLEEP_INTERVAL)

            # Variables used for the GET request.
            request_url = '{}/integrationServices/v3/cblr/session/{}'.format(self.CB_ROOT_URL, session_id)
            header = {'X-Auth-Token': self.CB_XAUTH_TOKEN}

            # Sends GET request to check on a CB Session
            response = requests.get(request_url,
                                    headers=header,
                                    verify=False,
                                    timeout=180)

            # Check if it was a valid response.
            if response.status_code == 200:
                # # Debug log
                # print("[RUNNING] Checking on CB session for {} ({}). Attempt #{}".format(sensor_name, session_id, int((count+2)/2)))

                # This is to check if the session is active.
                results = json.loads((response.content).decode())

                # Confirms if there is an active LR Session or not.
                # If it says PENDING, we should wait for a session
                # ID to spin up. 
                if results.get('status') == "ACTIVE":
                    # print("[DONE] CB Session for {} is 'ACTIVE'!".format(sensor_name))
                    return True

            # Keep adding to the counter to exit.
            count += self.SLEEP_INTERVAL

        # Assuming no live session could be established after 2 minutes
        return False

    def session_close(self, session_id, sensor_name):
        '''
        This closes an 'ACTIVE' CB session.
        '''

        request_url = '{}/integrationServices/v3/cblr/session'.format(self.CB_ROOT_URL)

        payload = "{\"session_id\": \"%s\",\"status\": \"CLOSE\"}" % session_id
        header = {'X-Auth-Token': self.CB_XAUTH_TOKEN,
                  'Content-Type': "application/json"}

        response = requests.put(request_url,
                                data=payload,
                                headers=header,
                                verify=False,
                                timeout=180)

        # FUTURE ADDITION. CHECK IF SESSION SUCCESSFULLY CLOSED.
        # if response.status_code == 200:
        #     # Successfully closed
        #     pass

        # else:
        #     # Do something since it may or may have not closed.
        #     pass

    def session_open(self, sensor_id, sensor_name):
        '''
        This opens up a session for CB.
        '''

        # Variables used for the POST request.
        request_url = '{}/integrationServices/v3/cblr/session/{}'.format(self.CB_ROOT_URL, sensor_id)
        header = {'X-Auth-Token': self.CB_XAUTH_TOKEN}

        # Sends POST request to obtain a CB Session ID
        response = requests.post(request_url,
                                 headers=header,
                                 verify=False,
                                 timeout=180)

        # Check if it was a valid response.
        if response.status_code == 200:

            # This is to check if the session is active.
            results = json.loads((response.content).decode())

            # Confirms if there is an active LR Session or not.
            # If it says PENDING, we should wait for a session
            # ID to spin up. 
            if results.get('status') == "PENDING":
                session_id_flag = self.session_check(results.get('id'), sensor_name)

                # Check if the system is online and we have an
                # active session.
                if session_id_flag == True:
                    return results.get('id')

                else:
                    return -1


            # If it's already active, just give back the session
            # id and continue with work.
            elif results.get('status') == "ACTIVE":
                return results.get('id')

            # Something else funky. Have not gotten to this point.
            else:
                return -1
        
        # Return all other status codes.
        else:
            return response.status_code

    def command_execute(self, session_id, sensor_name):
        '''
        Executes a command in CB and you should get an ID
        to check the status of it.
        '''

        # Variables used for the POST request.
        request_url = '{}/integrationServices/v3/cblr/session/{}/command'.format(self.CB_ROOT_URL, session_id)
        header = {'X-Auth-Token': self.CB_XAUTH_TOKEN,
                  'Content-Type': "application/json"}
        body = {"session_id": session_id,
                "name": "create process",
                "wait": "true",
                "object": self.command}

        # Sends POST request to obtain execute a command
        response = requests.post(request_url,
                                 headers=header,
                                 data=json.dumps(body),
                                 verify=False,
                                 timeout=180)

        # Makes sure we get a successful response.
        if response.status_code == 200:
            # Gets the command id
            command_id = json.loads((response.content).decode()).get('id')

            # Check command and return results.
            return self.command_check(session_id, sensor_name, command_id)

    def command_check(self, session_id, sensor_name, command_id):
        '''
        Checks command status to make sure it finishes
        '''
        # This counter is to make sure that this does not die.
        # It should never die, but you never know.
        count = 0 

        # This is to try a request every 2 seconds.
        while count < self.WAITING_PERIOD:
            # Sleep for interval in seconds
            time.sleep(self.SLEEP_INTERVAL)

            # Variables used for the POST request.
            request_url = '{}/integrationServices/v3/cblr/session/{}/command/{}'.format(self.CB_ROOT_URL, session_id, command_id)
            header = {'X-Auth-Token': self.CB_XAUTH_TOKEN,
                      'Content-Type': "application/json"}

            # Sends GET request to obtain command execution status
            response = requests.get(request_url,
                                    headers=header,
                                    verify=False,
                                    timeout=180)

            # Makes sure we get a successful response
            if response.status_code == 200:
                # # Debug log
                # print("[RUNNING] Checking on CB command for {} ({}). Attempt #{}".format(sensor_name, session_id, int((count+2)/2)))

                # Checks if the command has completed or not.
                if json.loads((response.content).decode()).get('status') == "complete":
                    return True

            # Keep adding to the counter to exit.
            count += self.SLEEP_INTERVAL

        # Assuming no live session could be established after
        # the waiting period.
        return False

    def upload_file_to_cb(self, session_id, sensor_name):
        '''
        Uploads a file to the CB server to then push to
        the systems reporting in CB.
        '''
        # Variables used for the POST request.
        request_url = '{}/integrationServices/v3/cblr/session/{}/file'.format(self.CB_ROOT_URL, session_id)

        header = {'X-Auth-Token': self.CB_XAUTH_TOKEN}

        upload_file = {'file': open(self.upload_file, 'rb')}

        # Sends POST request to obtain a file
        response = requests.post(request_url,
                                 headers=header,
                                 files=upload_file,
                                 verify=False,
                                 timeout=180)

        # Makes sure we get a successful response.
        if response.status_code == 200:
            # Gets the file id.
            file_id = json.loads((response.content).decode()).get('id')

            # Returns True or False if upload worked well.
            return self.put_file_request(session_id, sensor_name, file_id)

        else:
            return False

    def put_file_request(self, session_id, sensor_name, file_id):
        '''
        Puts file on the system.
        '''
        # Extract the filename. Remove all path.
        file_name = ((self.upload_file).split('/'))[-1]
        upload_file = 'C:\\Windows\\Temp\\{}'.format(file_name)

        # Variables used for the POST request.
        request_url = '{}/integrationServices/v3/cblr/session/{}/command'.format(self.CB_ROOT_URL, session_id)

        header = {'X-Auth-Token': self.CB_XAUTH_TOKEN,
                  'Content-Type': "application/json"}

        body = {"file_id": file_id,
                "name": "put file",
                "object": upload_file}

        # Sends POST request to obtain a file
        response = requests.post(request_url,
                                 headers=header,
                                 data=json.dumps(body),
                                 verify=False,
                                 timeout=180)

        # Makes sure we get a successful response.
        if response.status_code == 200:
            # Gets the command id.
            file_upload_id = json.loads((response.content).decode()).get('id')

            # Checks status until done.
            return self.put_file_check(session_id, sensor_name, file_upload_id)

        else:
            return False

    def put_file_check(self, session_id, sensor_name, file_upload_id):
        '''
        Checks status of the file for download
        '''
        # This counter is to make sure that this does not die.
        # It should never die, but you never know.
        count = 0 

        # This is to try a request every 2 seconds for every 5 minutes.
        while count < self.WAITING_PERIOD:
            # Sleep for interval in seconds
            time.sleep(self.SLEEP_INTERVAL)

            # Variables used for the POST request.
            request_url = '{}/integrationServices/v3/cblr/session/{}/command/{}'.format(self.CB_ROOT_URL, session_id, file_upload_id)
            header = {'X-Auth-Token': self.CB_XAUTH_TOKEN,
                      'Content-Type': "application/json"}

            # Sends GET request to obtain command execution status
            response = requests.get(request_url,
                                    headers=header,
                                    verify=False,
                                    timeout=180)

            # Makes sure we get a successful response
            if response.status_code == 200:
                # Checks if the command has completed or not.
                if json.loads((response.content).decode()).get('status') == "complete":
                    return True

            # Keep adding to the counter to exit.
            count += self.SLEEP_INTERVAL

        # Assuming no live session could be established after 2 minutes
        return False

    def get_file_request(self, session_id, sensor_name):
        '''
        Grabs a file from CB. It needs to execute a
        command, and check.
        '''

        # Variables used for the POST request.
        request_url = '{}/integrationServices/v3/cblr/session/{}/command'.format(self.CB_ROOT_URL, session_id)

        header = {'X-Auth-Token': self.CB_XAUTH_TOKEN,
                  'Content-Type': "application/json"}

        body = {"session_id": session_id,
                    "name": "get file",
                    "object": self.out_file}

        # Sends POST request to obtain a file
        response = requests.post(request_url,
                                 headers=header,
                                 data=json.dumps(body),
                                 verify=False,
                                 timeout=180)

        # Makes sure we get a successful response.
        if response.status_code == 200:
            # Gets the command id.
            command_id = json.loads((response.content).decode()).get('id')

            # Collects the file_id for download.
            file_id = self.get_file_check(session_id, sensor_name, command_id)

            # If no file_id, then return that there was an error.
            if file_id == False:
                return False

            # Otherwise, we have file_id, let's download this puppy.
            else:
                file_download_status = self.get_file_download(session_id, sensor_name, file_id)

                if file_download_status == False:
                    return False

            return True

        else:
            return False

    def get_file_check(self, session_id, sensor_name, command_id):
        '''
        Checks status of the file for download
        '''
        # This counter is to make sure that this does not die.
        # It should never die, but you never know.
        count = 0 

        # This is to try a request every 2 seconds for every 5 minutes.
        while count < self.WAITING_PERIOD:
            # Sleep for interval in seconds
            time.sleep(self.SLEEP_INTERVAL)

            # Variables used for the POST request.
            request_url = '{}/integrationServices/v3/cblr/session/{}/command/{}'.format(self.CB_ROOT_URL, session_id, command_id)
            header = {'X-Auth-Token': self.CB_XAUTH_TOKEN,
                      'Content-Type': "application/json"}

            # Sends GET request to obtain command execution status
            response = requests.get(request_url,
                                    headers=header,
                                    verify=False,
                                    timeout=180)

            # Makes sure we get a successful response
            if response.status_code == 200:
                # Checks if the command has completed or not.
                if json.loads((response.content).decode()).get('status') == "complete":
                    return json.loads((response.content).decode()).get('file_id')

            # Keep adding to the counter to exit.
            count += self.SLEEP_INTERVAL

        # Assuming no live session could be established after 2 minutes
        return False

    def get_file_download(self, session_id, sensor_name, file_id):
        '''
        Downloads file to directory
        '''
        # Checks if directory exists before dumping to folder.
        output_folder = "{}/{}_{}".format(OUTPUT_DIRECTORY, self.TUID, (self.sweep_name).replace(' ', '_'))
        hunt_file_stripped = ((self.out_file).split('\\')[-1]).replace(' ', '_')
        output_filename = "{}_{}".format(sensor_name, hunt_file_stripped)
        output_file_path = "{}/{}".format(output_folder, output_filename)

        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        # Variables used for the POST request.
        request_url = '{}/integrationServices/v3/cblr/session/{}/file/{}/content'.format(self.CB_ROOT_URL, session_id, file_id)

        header = {'X-Auth-Token': self.CB_XAUTH_TOKEN,
                  'Content-Type': "application/json"}

        # Sends POST request to obtain a file
        response = requests.get(request_url,
                                headers=header,
                                verify=False,
                                timeout=180)

        if response.status_code == 200:
            # Saves file to directory.
            with open(output_file_path, "wb") as ofile:
                # Write file to disk.
                ofile.write(response.content)

            return True

        else:
            return False

    def get_sweep_log_host_id(self, device_id):
        '''
        Gets the host information for one host host in the
        sweep_log from the MongoDB database.
        '''
        # Queries Mongo for the host in the sweep_log.
        return CB_BOT_DB.sweep_log.find_one({"device_id": int(device_id), "tuid": int(self.TUID)})['_id']

    def update_one_host_sweep(self, data_type, data_value, _id):
        '''
        Updated a field for a host in the sweep_log collection.

        :param data_type:
        :param data_value:
        :param _id:
        '''

        # Updates the record for a host in the sweep_log collection.
        CB_BOT_DB.sweep_log.update_one({'_id': _id},
                                     {'$set': {data_type: data_value}},
                                     upsert=False)

    def get_host_last_reported_time(self, sensor_id):
        '''
        This queries the CB API for the host's last reported
        timestamp. Once we have that we can cross check the
        minimum checking time selected.
        '''

        # Variables used for the GET request.
        request_url = '{}/integrationServices/v3/device/{}'.format(self.CB_ROOT_URL, sensor_id)
        header = {'X-Auth-Token': self.CB_XAUTH_TOKEN}

        # Sends GET request to check on a CB Session
        response = requests.get(request_url,
                                headers=header,
                                verify=False,
                                timeout=180)

        # Check if it was a valid response.
        if response.status_code == 200:
            # This is to check if the sensor is listed. Most likely yes.
            results = json.loads((response.content).decode())

            # Confirms if there is an active LR Session or not.
            # If it says PENDING, we should wait for a session
            # ID to spin up. 
            if results.get('success') == True:
                return datetime.datetime.utcfromtimestamp((int(results['deviceInfo']['lastReportedTime'])/1000))

            else:
                return False

    def update_completed_hosts_task(self):
        '''
        Updates the count of hosts that have been completed
        on a particular sweep.
        '''
        # Check on completed host count
        completed_count = len(list(CB_BOT_DB.sweep_log.find({"tuid": int(self.TUID), "complete": True})))

        # Change the completed_hosts count on the specific task.
        update_task('completed_hosts', completed_count, self.task_object_id)

    def delete_file(self, session_id, sensor_name, file_to_delete):
        '''
        Deletes the file created on disk.
        '''
        # # Debug Log
        # print("[RUNNING] Grabbing output file on %s" % (sensor_name))

        # Variables used for the POST request.
        request_url = '{}/integrationServices/v3/cblr/session/{}/command'.format(self.CB_ROOT_URL, session_id)

        header = {'X-Auth-Token': self.CB_XAUTH_TOKEN,
                  'Content-Type': "application/json"}

        body = {"session_id": session_id,
                "name": "delete file",
                "object": file_to_delete}

        # Sends POST request to obtain a file
        response = requests.post(request_url,
                                 headers=header,
                                 data=json.dumps(body),
                                 verify=False,
                                 timeout=180)

        # Makes sure we get a successful response.
        if response.status_code == 200:
            # print("[DONE] File deleted on %s" % (sensor_name))
            return

        else:
            # print("[ERROR] Error encountered deleting '%s' from %s" % (output_file, sensor_name))
            # ERROR_HOSTS.append({sensor_name:session_id.split(':')[1]})
            return

def add_hosts_to_sweep_log(host_list, device_type):
    '''
    Adds hosts to the sweep_log collection.

    :params host_list:
    :params TUID:
    :params device_type:

    :return sweep_host_list:
    '''

    # Define function variable.
    sweep_host_list = list()

    # Iterate through all the hosts and add to sweep_log collection.
    for host in host_list:
        # Depending on the script/command to run, we want to make
        # sure that we are running it on the proper operating system.
        if host['device_type'] == device_type:
            entry = dict()
            entry['hostname'] = host['hostname']
            entry['device_id'] = host['device_id']
            entry['complete'] = False
            entry['status'] = "Not started"
            entry['completed_timestamp'] = 'N/A'
            entry['tuid'] = TUID

            # Adds the log entry to the sweep_log collection.
            CB_BOT_DB.sweep_log.insert_one(entry)

            # Adds host to the sweep_host_list variable.
            sweep_host_list.append({host['hostname']: host['device_id']})

    # Return the sweep_host_List
    return sweep_host_list

def get_command_specs():
    '''
    Gets the command specifications given the proper command id.

    :returns command_specs:
    '''

    return CB_BOT_DB.sweep_commands.find_one({"cuid": {"$eq": CUID}})

def get_hosts_to_sweep(device_type):
    '''
    Checks if the sweep has already existed and systems have been
    added to the sweep log. If the systems are not in the sweep
    log then it means that this sweep/task was never run. If they
    are, we can just resume on what is left.

    :params TUID:
    :return hosts:
    '''
    # Define variables used in the function
    sweep_host_list = list()
    results = list(CB_BOT_DB.sweep_log.find({"tuid": {"$eq": int(TUID)}}).collation({ "locale": "en_US", "strength": 1 }).sort('hostname', pymongo.DESCENDING))

    # If this is a new sweep, let's add all the hosts that are in
    # CB into the sweep_log and let's get a list of the pair of
    # hostname and device_id.
    if len(results) == 0:
        hosts = list(CB_BOT_DB.endpoints.find().collation({ "locale": "en_US", "strength": 1 }).sort('last_reported_time', pymongo.DESCENDING))
        sweep_host_list = add_hosts_to_sweep_log(hosts, device_type)

    # This will follow through if there is data for that specific
    # sweep.
    else:
        # ========= DEV =========
        print("Sweep exists. Extracting host list.")
        # ========= DEV =========

        # Iterate through all the hosts and extract their device_id.
        for host in results:
            if host['complete'] == False:
                sweep_host_list.append({host['hostname']: host['device_id']})

    # Return all of the hosts that we are going to be sweeping for
    # in this sweep run/task.
    return sweep_host_list

def start_queue(host_list, command_specs, _id, sweep_name):
    '''
    Starts a multi-threaded queue using all of
    the sensors in the sensor list. This way you
    can call up the process to run your action
    in CB.
    '''
    # Update the MongoDB details for the task
    total_hosts = get_sweep_log_host_count()
    update_task('total_hosts', total_hosts, _id)

    # Create a master dictionary to return.
    # Defines the queue
    queue_list = queue.Queue()

    try:
        # Add each of the sensors to the queue
        for obj in host_list:
            obj = dict(obj)

            for sensor_name, sensor_id in obj.items():
                item = '{}||{}'.format(sensor_name, sensor_id)
                queue_list.put(item)

        # If no sensors in list, return
        if queue.Queue.qsize(queue_list) == 0:
            return

        # print("Queue size: {}".format(queue.Queue.qsize(queue_list)))
        # quit()

        workers_list = []
        total_hosts = queue.Queue.qsize(queue_list)

        for i in range(CB_CONCURRENT_SESSIONS):
            # Start multi-threading and run "run_cb_gather" function
            # to start running the query that we want it to do.
            cb_bot_worker = CB_BOT(queue_list, total_hosts, command_specs, _id, sweep_name)
            worker = threading.Thread(target=cb_bot_worker.run_sweep, daemon=True)
            worker.start()
            workers_list.append(worker)
        queue_list.join()

    except Exception as e:
        print("Error at 'start_queue' function: {}".format(e))

def get_sweep_log_host_count():
    '''
    Get host count on all of the hosts for a
    specific TUID. 
    '''

    return CB_BOT_DB.sweep_log.count({"tuid": TUID})

def update_task(data_type, data_value, _id):
    '''
    Updated a field for a task in the task_history collection.

    :param data_type:
    :param data_value:
    :param _id:
    '''

    # Updates the record for the task.
    CB_BOT_DB.task_history.update_one({'_id': _id},
                                    {'$set': {data_type: data_value}},
                                    upsert=False)

def get_task_object_id():
    '''
    Gets the task information for one task from
    the MongoDB database.
    '''
    # Queries Mongo for the task.
    return CB_BOT_DB.task_history.find_one({'tuid': int(TUID)})

def get_task_owner():
    '''
    Gets the task information for one task from
    the MongoDB database.
    '''
    # Queries Mongo for the task.
    return (CB_BOT_DB.task_history.find_one({'tuid': int(TUID)})['owner'])

def create_alert(alert):
    '''
    Adds an alert to the MongoDB database 'alerts'
    collection

    :param alert:
    '''

    # Adds the log entry to the alerts collection.
    CB_BOT_DB.alerts.insert_one(alert)

def get_largest_auid():
    '''
    Gets the largest AUID for the users in the database.
    
    :return auid:
    '''

    # Queries the MongoDB database for the largest AUID
    user_list = list(CB_BOT_DB.alerts.find({}).sort('auid', pymongo.DESCENDING))

    # Checks if there are no AUIDs.
    if len(user_list) == 0:
        return 0

    return user_list[0]['auid']

def main():
    '''
    Main function for cb_bot.
    '''

    # Gets information about the command.
    command_specs = get_command_specs()

    # Gets information about the task.
    _id = get_task_object_id()["_id"]
    sweep_name = get_task_object_id()["name"]

    # Check if we are restarting the script on the remaining
    # hosts or if we haven't created anything at all.
    host_list = get_hosts_to_sweep(command_specs['device_type'])

    # Checks if the hostlist is blank or not before proceeding.
    # If no hosts, quit.
    if len(host_list) == 0:
        print("[*] There are no hosts available to sweep")
        # Change Task status to inactive and terminate the program.
        update_task('active', False, _id)

        # Create an alert.
        alert = dict()
        auid = get_largest_auid() + 1
        timestamp = datetime.datetime.utcnow()
        alert['created'] = timestamp
        alert['message_date'] = timestamp.strftime("%B %d, %Y  %-I:%M %p UTC")
        alert['active'] = True
        alert['owner'] = get_task_owner()
        alert['auid'] = auid
        alert['message'] = "Failed Sweep with Task ID {}: {}. There are no hosts! Refresh host list before continuing.".format(TUID, sweep_name)

        # Tell Mongo to add alert.
        create_alert(alert)

        quit()

    # # ========= DEV =========
    # print("Running sweep on {} hosts.".format(len(host_list)))
    # # ========= DEV =========

    # Initiates the multi-threading process.
    start_queue(host_list, command_specs, _id, sweep_name)

    # Add template for initial alert. Then we will need to change
    # this to True.
    alert = dict()
    auid = get_largest_auid() + 1
    timestamp = datetime.datetime.utcnow()
    alert['created'] = timestamp
    alert['message_date'] = timestamp.strftime("%B %d, %Y  %-I:%M %p UTC")
    alert['active'] = False
    alert['owner'] = get_task_owner()
    alert['auid'] = auid
    alert['message'] = "Completed Sweep with Task ID {}: {}.".format(TUID, sweep_name)

    # Tell Mongo to add alert.
    create_alert(alert)

    # Change Task status to inactive and terminate the program.
    update_task('active', False, _id)
    
if __name__ == '__main__':
    main()
