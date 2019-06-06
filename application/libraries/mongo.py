import pymongo

from application import app

#########################################
#           MONGODB API CALLS           #
#########################################
def add_alert(alert):
    '''
    Adds an alert to the MongoDB database 'alerts'
    collection

    :param alert:
    '''

    # Adds the log entry to the alerts collection.
    app.config['DOBY_DB'].alerts.insert(alert)

def add_sweep(sweep):
    '''
    Adds a sweep command to the MongoDB database 'sweep_commands'
    collection

    :param sweep:
    '''

    # Adds the log entry to the sweep_commands collection.
    app.config['DOBY_DB'].sweep_commands.insert(sweep)

def add_log_entry(timestamp, ip, user, account_type, page, message):
    '''
    Adds a log entry into the databse which will include
    the following four items.

    :param timestamp:
    :param ip:
    :param user:
    :param account_type:
    :param page:
    :param message:
    '''

    # Adds the log entry to the activity_logs collection.
    app.config['DOBY_DB'].activity_logs.insert({'timestamp': timestamp,
                                                'source_ip': ip,
                                                'user': user,
                                                'account_type': account_type,
                                                'page': page,
                                                'message': message})

def add_task(task):
    '''
    Adds a task to the MongoDB database 'task_history'
    collection

    :param task:
    '''

    # Adds the log entry to the task_history collection.
    app.config['DOBY_DB'].task_history.insert(task)

def add_user(user):
    '''
    Adds a user to the MongoDB database 'users'
    collection

    :param user:
    '''

    # Adds the log entry to the user collection.
    app.config['DOBY_DB'].users.insert(user)

def get_all_alerts_active_user(user):
    '''
    Gets all of the active alerts for a specific user in CB.

    :param user:
    :return alerts:
    '''

    return list(app.config['DOBY_DB'].alerts.find({"owner": {"$eq": user}, "active": {"$eq": True}}).sort('created', pymongo.DESCENDING))

def get_all_cb_hosts():
    '''
    Gets all of the hostnames that are reporting to CB.
    '''
    
    return list(app.config['DOBY_DB'].cb_hosts.find().collation({ "locale": "en_US", "strength": 1 }).sort('hostname', pymongo.ASCENDING))

def get_all_log_entries():
    '''
    Gets all of the log entries for all users.
    '''
    
    return list(app.config['DOBY_DB'].activity_logs.find({}).sort('timestamp', pymongo.DESCENDING))

def get_all_user_log_entries(user):
    '''
    Gets all of the log entries for one specific user.
    '''
    
    return list(app.config['DOBY_DB'].activity_logs.find({'user': user}).sort('timestamp', pymongo.DESCENDING))

def get_all_sweeps():
    '''
    Gets all of the sweeps that were run on this CB instance.
    '''
    
    return list(app.config['DOBY_DB'].task_history.find({"task": {"$eq": "sweep"}}).collation({ "locale": "en_US", "strength": 1 }).sort('tuid', pymongo.DESCENDING))

def get_all_sweep_commands():
    '''
    Gets all of the sweep commands
    '''
    
    return list(app.config['DOBY_DB'].sweep_commands.find({}).collation({ "locale": "en_US", "strength": 1 }).sort('name', pymongo.DESCENDING))

def get_all_sweep_hosts(tuid):
    '''
    Gets all of the hosts associated to a sweep/task by
    querying the sweep_log collection.

    :params tuid:
    :return hosts:
    '''
    
    return list(app.config['DOBY_DB'].sweep_log.find({"tuid": {"$eq": tuid}}).collation({ "locale": "en_US", "strength": 1 }).sort('hostname', pymongo.DESCENDING))

def get_all_sweeps_active():
    '''
    Gets all of the active sweeps that were run on this CB instance.
    '''
    
    return list(app.config['DOBY_DB'].task_history.find({"task": {"$eq": "revelio"}, "active": {"$eq": True}}).collation({ "locale": "en_US", "strength": 1 }).sort('name', pymongo.DESCENDING))

def get_all_jobs():
    '''
    Gets all of the jobs that were run on this CB instance.
    '''
    
    return list(app.config['DOBY_DB'].task_history.find({"task": {"$eq": "job"}}).collation({ "locale": "en_US", "strength": 1 }).sort('name', pymongo.DESCENDING))

def get_all_tasks():
    '''
    Gets all of the tasks that were run on this CB instance.
    '''

    return list(app.config['DOBY_DB'].task_history.find({}).collation({ "locale": "en_US", "strength": 1 }).sort('created', pymongo.DESCENDING))

def get_all_tasks_active():
    '''
    Gets all of the active tasks that were run on this CB instance.
    '''

    return list(app.config['DOBY_DB'].task_history.find({"active": {"$eq": True}}).collation({ "locale": "en_US", "strength": 1 }).sort('created', pymongo.DESCENDING))

def get_all_host_list_refresh_job():
    '''
    Gets a list of the jobs that were run that refreshed the
    host list.
    '''

    return list(app.config['DOBY_DB'].task_history.find({"task": {"$eq": "job"}, "type": {"$eq": "Refresh Host List"}}).collation({ "locale": "en_US", "strength": 1 }).sort('created', pymongo.DESCENDING))

def get_all_users():
    '''
    Gets all of the users for this Doby instance.
    '''

    # Return all users
    return list(app.config['DOBY_DB'].users.find({}).collation({ "locale": "en_US", "strength": 1 }).sort('uuid', pymongo.DESCENDING))

def get_server_settings():
    '''
    Gets the CB Server Configuration fro mthe MongoDB database.
    '''
    
    # Get configuration from the MongoDB. There should only be
    # one item or none. Potential implementation of multiple
    # CB Server Configuration is possible, just not implemented yet.
    list_data = list(app.config['DOBY_DB'].server_settings.find({"name": {"$eq": "Carbon Black"}}))

    # Determines if there is data to be sent back. If there
    # are no configurations set, then it should return blank.
    if len(list_data) > 0:
        return list_data[0]
    
    else:
        return ""

def get_giphy_settings():
    '''
    Gets the Giphy Settings fro mthe MongoDB database.
    '''
    
    # Get configuration from the MongoDB. There should only be
    # one item or none. 
    list_data = list(app.config['DOBY_DB'].server_settings.find({"name": {"$eq": "Giphy"}}))

    # Determines if there is data to be sent back. If there
    # are no configurations set, then it should return blank.
    if len(list_data) > 0:
        return list_data[0]
    
    else:
        return ""

def get_largest_cuid():
    '''
    Gets the largest CUID for the tasks in the database.
    
    :return tuid:
    '''

    # Queries the MongoDB database for the largest CUIDs.
    task_list = list(app.config['DOBY_DB'].sweep_commands.find({}).sort('cuid', pymongo.DESCENDING))

    # Checks if there are no CUIDs. If none, return 0.
    if len(task_list) == 0:
        return 0

    return task_list[0]['tuid']

def get_largest_tuid():
    '''
    Gets the largest TUID for the tasks in the database.
    
    :return tuid:
    '''

    # Queries the MongoDB database for the largest TUIDs.
    task_list = list(app.config['DOBY_DB'].task_history.find({}).sort('tuid', pymongo.DESCENDING))

    # Checks if there are no TUIDs. If none, return 0.
    if len(task_list) == 0:
        return 0

    return task_list[0]['tuid']

def get_largest_uuid():
    '''
    Gets the largest UUID for the users in the database.
    
    :return uuid:
    '''

    # Queries the MongoDB database for the largest UUID
    user_list = list(app.config['DOBY_DB'].users.find({}).sort('uuid', pymongo.DESCENDING))

    # Checks if there are no UUIDs. If none, return 0.
    if len(user_list) == 0:
        return 0

    return user_list[0]['uuid']

def get_largest_auid():
    '''
    Gets the largest AUID for the users in the database.
    
    :return auid:
    '''

    # Queries the MongoDB database for the largest AUID
    alert_list = list(app.config['DOBY_DB'].users.find({}).sort('auid', pymongo.DESCENDING))

    # Checks if there are no AUIDs. If none, return 0.
    if len(alert_list) == 0:
        return 0

    return alert_list[0]['auid']

def get_one_command(cuid):
    '''
    Gets the command specifications given the proper command id.

    :params cuid:

    :returns command_specs:
    '''

    return app.config['DOBY_DB'].sweep_commands.find_one({"cuid": {"$eq": int(cuid)}})

def get_one_case():
    '''
    Gets the case name or number for the investigation.
    
    :return case:
    '''

    # Queries the MongoDB database for any information regarding
    # the case name.
    return app.config['DOBY_DB'].server_settings.find_one({'name': 'Doby'})

    # results = app.config['DOBY_DB'].server_settings.find_one({'name': 'Doby'})

def get_one_task(data_type, data_value):
    '''
    Gets the task information using a value and type
    that exists in the database.
    
    :param data_type:
    :param data_value:
    :return task_data:
    '''

    # Queries the MongoDB database for any information regarding
    # the TUID at question.
    return app.config['DOBY_DB'].task_history.find_one({data_type: data_value})

def get_one_user_info(data_type, data_value):
    '''
    Gets the user information using a value and type
    that exists in the database.
    
    :param data_type:
    :param data_value:
    :return user_data:
    '''

    # Queries the MongoDB database for any information regarding
    # the email account at question.
    return app.config['DOBY_DB'].users.find_one({data_type: data_value})

def get_one_alert(data_type, data_value):
    '''
    Gets the alert information using a value and type
    that exists in the database.
    
    :param data_type:
    :param data_value:
    :return alert_data:
    '''

    # Queries the MongoDB database for any information regarding
    # the TUID at question.
    return app.config['DOBY_DB'].alerts.find_one({data_type: data_value})

def update_server_settings(_id, data_type, data_value):
    '''
    Updates CB Server Configuration' configuration details.

    :param _id:
    :param data_type:
    :param data_value:
    '''

    # Updates the record for the user.
    app.config['DOBY_DB'].server_settings.update_one({'_id': _id},
                                                        {'$set': {data_type: data_value}},
                                                        upsert=False)

def update_user_info(_id, data_type, data_value):
    '''
    Updates a user's information by using a value and type
    that exists in the database.

    :param _id:
    :param data_type:
    :param data_value:
    '''

    # Updates the record for the user.
    app.config['DOBY_DB'].users.update_one({'_id': _id},
                                           {'$set': {data_type: data_value}},
                                           upsert=False)

def update_alert_id(_id, data_type, data_value):
    '''
    Updates an alert to False sent usually by the click of
    a link in the alerts section.

    :param _id:
    :param data_type:
    :param data_value:
    '''

    # Updates the record for the user.
    app.config['DOBY_DB'].alerts.update_one({'_id': _id},
                                            {'$set': {data_type: data_value}},
                                             upsert=False)

def update_task(data_type, data_value, _id):
    '''
    Updated a field for a task in the task_history collection.

    :param data_type:
    :param data_value:
    :param _id:
    '''

    # Updates the record for the task.
    app.config['DOBY_DB'].task_history.update_one({'_id': _id},
                                    {'$set': {data_type: data_value}},
                                    upsert=False)