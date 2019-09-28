import datetime
import json
import queue
import sys
import threading

import pymongo
import requests

requests.packages.urllib3.disable_warnings()

# Database configuration
MONGO_CLIENT = pymongo.MongoClient('127.0.0.1', 5051)
CB_BOT_DB = MONGO_CLIENT.cb_bot

class CB_BOT():

    def __init__(self, queue_list, total_hosts, _id, auid, CB_ROOT_URL, CB_XAUTH_TOKEN):
        self.queue_list = queue_list
        self.sensor_data = dict()
        self.total_hosts = total_hosts
        self._id = _id
        self.auid = auid
        self.CB_ROOT_URL = CB_ROOT_URL
        self.CB_XAUTH_TOKEN = CB_XAUTH_TOKEN

    def add_one_host(self, sensor):
        '''
        Adds a sensor/host to the 'endpoints' collection

        :param sensor:
        '''

        # Adds the log entry to the activity_logs collection.
        CB_BOT_DB.endpoints.insert_one(sensor)

    def get_host_validity(self, sensor_data):
        '''
        Checks if the host exists in the MongoDB database.
        '''
        # Validate quickly if there is no hostname value
        # to just return false and process it.
        if sensor_data == None or len(sensor_data) == 0:
            return False

        # Queries to see if the host exists. It may be sensor data
        # or just the hostname being passed. We also validate
        # that here.
        if sensor_data is dict():
            results = list(CB_BOT_DB.endpoints.find({"hostname": { "$eq": sensor_data.get('deviceName') } }))
        else:
            results = list(CB_BOT_DB.endpoints.find({"hostname": { "$eq": sensor_data } }))

        # If the count of results is greater than 0 (usually 1), then
        # it should return that host exists. Otherwise, return false.
        if len(results) > 0:
            # Get the right timestamp format before sending
            # to the MongoDB
            if sensor_data is dict():
                try:
                    timestamp_str = '{} {}'.format(sensor_data.get('lastCheckInDate'), sensor_data.get('lastCheckInTime'))
                    last_reported_time = datetime.datetime.strptime(timestamp_str, '%Y%m%d %H%M%S')

                # This is just to catch if no timestamps were provided. 
                except:
                    last_reported_time = "N/A"

                # Update last check-in time.
                self.update_one_sensor('last_reported_time', last_reported_time, results[0]['_id'])

            # Return that system exists
            return True
        
        else:
            # Return that system does not exist.
            return False

    def get_one_alert(self):
        '''
        Gets the alert information using a value and type
        that exists in the database.
        
        :param data_type:
        :param data_value:
        :return alert_data:
        '''

        # Queries the MongoDB database for any information regarding
        # the TUID at question.
        return CB_BOT_DB.alerts.find_one({'auid': self.auid})

    def get_one_sensor(self, hostname):
        '''
        Gets the basic information from one host.
        ''' 

        try:
            request_url = '{}/integrationServices/v3/device'.format(self.CB_ROOT_URL)
            header = {'X-Auth-Token': self.CB_XAUTH_TOKEN}
            parameters = {'hostNameExact': hostname}

            # Sends GET request to collect host information
            response = requests.get(request_url,
                                    headers=header,
                                    params=parameters,
                                    verify=False,
                                    timeout=180)

            # Checks if the status was successful.
            if response.status_code == 200:
                # Returns the information for the host
                return ((json.loads(response.content.decode())).get('results'))[0]

            else:
                # Returns status code if there was an error.
                return response.status_code

        except Exception as e:
            return -1

    def start_updating(self):

        # Ensures that there are no more elements in the Queue to be taking
        while queue.Queue.qsize(self.queue_list) != 0:

            # Gets data from the Queue List
            self.sensor_data = self.queue_list.get(timeout=1)

            # Check if the host has already been added to the database.
            flag = self.get_host_validity(self.sensor_data)

            # Updating the completed host count
            completed_hosts = (self.total_hosts - queue.Queue.qsize(self.queue_list))
            self.update_task_class('completed_hosts', completed_hosts, self._id)

            # If False, meaning there is no host in the database,
            # add it.
            if flag == False:

                # Gets the hostname.
                sensor_details = self.get_one_sensor(self.sensor_data.get('deviceName'))

                # This is just to ensure that there is data returning.
                if type(sensor_details) is dict:
                
                    # Define temporary ditionary for each system
                    system = dict()

                    # Assign the system information to the 'system'
                    # dictionary for further processing
                    system['hostname'] = sensor_details.get('name')
                    system['last_ip'] = sensor_details.get('lastInternalIpAddress')
                    system['device_id'] = sensor_details.get('deviceId')
                    system['device_type'] = sensor_details.get('deviceType')
                    system['os_version'] = sensor_details.get('osVersion')
                    system['policy_name'] = self.sensor_data.get('policyName')

                    # Get the right timestamp format before sending
                    # to the MongoDB
                    try:
                        timestamp_str = '{} {}'.format(self.sensor_data.get('lastCheckInDate'), self.sensor_data.get('lastCheckInTime'))
                        timestamp_obj = datetime.datetime.strptime(timestamp_str, '%Y%m%d %H%M%S')
                        system['last_reported_time'] = timestamp_obj

                    # This is just to catch if no timestamps were provided. 
                    except:
                        system['last_reported_time'] = "N/A"

                    # Checking if the hostname is actually there or not.
                    # Some cases CB returns none, but when querying a device,
                    # it will sometimes get another hostname
                    flag_host = self.get_host_validity(system['hostname'])

                    if flag_host == False:
                        # Adds the user to the MongoDB.
                        self.add_one_host(system)
                        
                    # Clear the 'system' variable.
                    system.clear()

                elif sensor_details == -1:
                    pass

                else:
                    # Just quit the application
                    quit()
            
            # Here we would need to update the host timestamp if possible.
            # Potential future implementation
            else:
                pass

        # HERE GOES THE CODE TO UPDATE THE ALERT.
        alert_data = self.get_one_alert()

        # Update timestamp completion.
        timestamp = datetime.datetime.utcnow()
        message_date = timestamp.strftime("%B %d, %Y  %-I:%M %p UTC")

        # Update existing alert.
        self.update_one_alert(alert_data['_id'], message_date, timestamp)

        # Update task to inactive.
        self.update_task_class('active', False, self._id)
        
    def update_one_alert(slef, _id, message_date, created):
        '''
        Updates an alert to False sent usually by the click of
        a link in the alerts section.

        :param _id:
        :param data_type:
        :param data_value:
        '''

        # Updates the record for the user.
        CB_BOT_DB.alerts.update_one({'_id': _id},
                                  {'$set': {'message_date': message_date,
                                            'created': created,
                                            'active': True}},
                                  upsert=False)

    def update_one_sensor(self, data_type, data_value, _id):
        '''
        Updated a field for a sensor in the host collection.

        :param data_type:
        :param data_value:
        :param _id:
        '''

        # Updates the record for the task.
        CB_BOT_DB.endpoints.update_one({'_id': _id},
                                    {'$set': {data_type: data_value}},
                                    upsert=False)

    def update_task_class(self, data_type, data_value, _id):
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

def get_all_sensors(CS_CONCURRENT_SESSIONS, CB_ROOT_URL, CB_XAUTH_TOKEN, _id, auid):
    '''
    Gets a list of all the sensors/computers registered to 
    the specific account. and returns a list with all of
    the necessary elements for our tool.
    '''
    request_url = '{}/integrationServices/v3/device/all'.format(CB_ROOT_URL)
    header = {'X-Auth-Token': CB_XAUTH_TOKEN}
    parameters = {'fileFormat': 'json'}

    # Sends GET request to collect host names
    response = requests.get(request_url,
                            headers=header,
                            params=parameters,
                            verify=False,
                            timeout=180)

    # Checks if the status was successful.
    if response.status_code == 200:

        # Get sensor list. All of the results are in
        # the "results" key.
        results = json.loads(response.content.decode())
        results = list(results.get('results'))

        # Update the MongoDB details for the task
        total_hosts = len(results)
        update_task('total_hosts', total_hosts, _id)

        # Create a master dictionary to return.
        # Defines the queue
        queue_list = queue.Queue()

        try:
            # Add each of the sensors to the queue
            for sensor in results:
                queue_list.put(sensor)

            # If no sensors in list, return
            if queue.Queue.qsize(queue_list) == 0:
                return

            workers_list = []
            total_hosts = queue.Queue.qsize(queue_list)

            for i in range(int(CS_CONCURRENT_SESSIONS)):
                # Start multi-threading and run "run_cb_gather" function
                # to start running the query that we want it to do.
                cb_bot_worker = CB_BOT(queue_list, total_hosts, _id, auid, CB_ROOT_URL, CB_XAUTH_TOKEN)
                worker = threading.Thread(target=cb_bot_worker.start_updating, daemon=True)
                worker.start()
                workers_list.append(worker)
            queue_list.join()

        except Exception as e:
            print("multithread")
            print(e)

    else:
        # Change Task status to inactive and terminate the program.
        update_task('active', False, _id)
        quit()

def get_server_settings():
    '''
    Gets the CB Server Configuration from the MongoDB database.
    '''
    
    # Get configuration from the MongoDB. There should only be
    # one item or none. Potential implementation of multiple
    # CB Server Configuration is possible, just not implemented yet.
    list_data = list(CB_BOT_DB.server_settings.find({"name" : "Carbon Black"}))

    # Determines if there is data to be sent back. If there
    # are no configurations set, then it should return blank.
    if len(list_data) > 0:
        return list_data[0]
    
    else:
        return ""

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

def get_task_object_id(tuid):
    '''
    Gets the task information for one task from
    the MongoDB database.
    '''
    # Queries Mongo for the task.
    return CB_BOT_DB.task_history.find_one({'tuid': int(tuid)})['_id']

def get_task_owner(tuid):
    '''
    Gets the task information for one task from
    the MongoDB database.
    '''
    # Queries Mongo for the task.
    return (CB_BOT_DB.task_history.find_one({'tuid': int(tuid)})['owner'])

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
    # Gets the CB settings from the database.
    config = get_server_settings()

    # Validate if config is empty or not before continuing
    # as it requires the DB configs to get sensor data.
    if config == '':
        quit()

    else:
        CB_ROOT_URL = config['root_url']
        CB_API_SECRET_KEY = config['api_secret_key']
        CB_API_ID = config['api_id']
        CB_XAUTH_TOKEN = '{}/{}'.format(CB_API_SECRET_KEY, CB_API_ID)
        CS_CONCURRENT_SESSIONS = config['max_sessions']

    # Get the _id from the task, given the TUID.
    tuid = sys.argv[1]
    _id = get_task_object_id(tuid)

    # Add template for initial alert. Then we will need to change
    # this to True.
    alert = dict()
    auid = get_largest_auid() + 1
    # timestamp = datetime.datetime.utcnow()
    # alert['message_date'] = timestamp.strftime("%B %d, %Y  %-I:%M %p UTC")

    alert['active'] = False
    alert['owner'] = get_task_owner(tuid)
    alert['auid'] = auid
    alert['message'] = "Completed Task ID {}: Refresh Endpoint List".format(tuid)

    # Tell Mongo to add alert.
    create_alert(alert)
    
    # Collect all of the sensors and their device IDs.
    get_all_sensors(CS_CONCURRENT_SESSIONS, CB_ROOT_URL, CB_XAUTH_TOKEN, _id, auid)

    # Change Task status to inactive and terminate the program.
    update_task('active', False, _id)
    
if __name__ == '__main__':
    main()
