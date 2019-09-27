CB Bot is a threat hunting and incident response web application framework for using with Carbon Black (CB) Defense. By leveraging CB Defense's REST APIs, CB Bot manages to build and run sweeps (hunts) across a CB instance! I created CB Bot with the main goal to automate and speed up the threat hunting and incident response process across an organization. Not only will it make it easier to run hunts or sweeps across a network, but also make it faster. Less time building tech, more time finding bad guys.


# Disclaimer
This disclaimer informs those that are reading, downloading, and using CB Bot that this code was written by me and does not represent my employer's views. My employer did not have any part or say in this project and everything that was done was as as side project of mine.


# Installation
_Note: Tested only on Ubuntu 18.04.3 (LTS) X64._

#### Step 1: Setting Up Your Server
Let's make sure that you have all the system updates, Python 3, and Mongo.

    apt-get update
    apt-get install -y mongodb python3 python3-pip
    
Go to the directory that you would like to clone CB Bot, and then use Git to clone the repository.

    git clone <repository>

#### Step 2: Installing CB-Bot Requirements
Once you've installed and downloaded all of the necessary files, let's jump into the CB Bot directory and install all the python libraries that CB Bot uses.

    cd cb-bot/setup
    pip3 install -r requirements.txt
    
I highly recommend you use a certificate of your own. However, if you do not have a certificate that you can use, you can create a self-signed certificate for CB Bot. I used these commands to create one for the demo server.

    openssl genrsa 4096 > /etc/ssl/private/cb_bot.key;
    openssl req -new -newkey rsa:4096 -days 365 -nodes -x509 -subj "/C=US/ST=TX/L=Austin/O=All Things DFIR" -key /etc/ssl/private/cb_bot.key -out /etc/ssl/certs/cb_bot.crt;

#### Step 3: Run "setup.py"
Finally, before you can get to use CB Bot, it's important to run "setup.py" to get the MongoDB configured with all the collections, the folders needed on the system, and the admin account used to log into the portal. Run it and follow all of the instructions.

    python3 setup.py
   
#### Step 4: Start CB Bot
After you have completed all of the steps above, just make sure to run CB Bot from the root directory of the application. If you've been following these instructions, then just do the following:

    cd ../
    python3 run.py

_Note: I recommend you running this as a process in the background if you want, or using `screen`. If so, run the command `screen -S <session_name>`, where `<session_name>` is the name of the session that you want to give it to.


# Configuration
Once you run CB Bot, go to address of where you have installed CB Bot and log in using the credentials that you supplied during Step 3 of the Installation section.
