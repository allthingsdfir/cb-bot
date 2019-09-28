# CB Bot
CB Bot is a threat hunting and incident response web application framework for using with Carbon Black (CB) Defense. By leveraging CB Defense's REST APIs, CB Bot can build and run sweeps (hunts) across a CB instance! I created CB Bot with the main goal to automate and speed up the threat hunting and incident response process across an organization. Not only will it make it easier to run hunts or sweeps across a network, but also make it faster. Let's spend less time building tech, and more time finding bad guys. :smile:	


# Disclaimer
This disclaimer informs those that are reading, downloading, and using CB Bot that this code was written by me and does not represent my employer's views. My employer did not have any part or say in this project and everything that was done was as as side project of mine.

# Requirements
### Hardware
Make sure you have at least the following:

CPU | RAM | Disk
------------ | ------------ | -------------
1 | 1 GB | 25 GB

Of course, the more you have, the better, but I've created a small instance in Digital Ocean and these are the specifications. I suggest you have more disk space, as sweeps can get pretty beefy if you have a large environment. 

### Network
Make sure that you apply the following inbound and outbound rules in order for CB Bot to work:

Protocol | Inbound | Outbound
------------ | ------------ | -------------
TCP | 22, 443 | 443, 9418

# Installation
_Note: Tested on Ubuntu 18.04.3 (LTS) x64._

### Step 1: Setting Up Your Server :electric_plug:
Let's make sure that you have all the system updates, Python 3, and Mongo.

    apt-get update
    apt-get install -y mongodb python3 python3-pip
    
Go to the directory that you would like to clone CB Bot, and then use Git to clone the repository.

    git clone <repository>

### Step 2: Installing CB-Bot Requirements :memo:
Once you've installed and downloaded all of the necessary files, let's jump into the CB Bot directory and install all the python libraries that CB Bot uses.

    cd cb-bot/setup
    pip3 install -r requirements.txt
    
I highly recommend you use a certificate of your own. However, if you do not have a certificate that you can use, you can create a self-signed certificate for CB Bot. I used these commands to create one for the demo server.

    openssl genrsa 4096 > /etc/ssl/private/cb_bot.key;
    openssl req -new -newkey rsa:4096 -days 365 -nodes -x509 -subj "/C=US/ST=TX/L=Austin/O=All Things DFIR" -key /etc/ssl/private/cb_bot.key -out /etc/ssl/certs/cb_bot.crt;
    
If you happen to use your own certs make sure you copy them to `/etc/ssl/private/cb_bot.key` and `/etc/ssl/certs/cb_bot.crt`. You can also save it in a different path, just make sure to edit the "run.py" file to reflect where the paths to the cert and key are.

**Important**: Go to the `application/__init__.py` file to change the `app.config['SECRET_KEY']` value. At the moment I have placed a generic value for testing, but this value should be changed and unique.

### Step 3: Run "setup.py" :runner:
Finally, before you can get to use CB Bot, it's important to run "setup.py" to get the MongoDB configured with all the collections, generate the folders needed on the system, and create the admin account used to log into the portal. Run it and follow all of the instructions.

    python3 setup.py

### Step 4: Start CB Bot :robot:
After you have completed all of the steps above, just make sure to run CB Bot from the root directory of the application. If you've been following these instructions, then just do the following:

    cd ../
    python3 run.py

_Note: I recommend you running this as a background process using `screen`. If so, run the command `screen -S <session_name>`, where `<session_name>` is the name of the session that you want to give it to. Then you can run CB Bot, then hit `Ctrl A + D` to detach from the session._


# Configuration
Once you run CB Bot, go to address of where you have installed CB Bot and log in using the credentials that you supplied during Step 3 of the Installation section. Now, once you successfully authenticate, you'll see something like the screenshot below. You'll notice that on the top right corner will be your name and a randomnly assigned avatar (you can change that in your profile settings). To the bottom right will be the `Administration` tab and once you click that new options are shown. Click on `Settings`.

![screenshot 1](/demo_screenshots/settings_section.png)

The `Settings` page will look like the screenshot below. Here you will have to put in your CB API Key and API Secret Key. Make sure to also include the root URL to your instance. For example, if you log in to your CB instance and the URL is something like `https://defense-prod01.conferdeploy.net/`, change the `Root URL` on the page to be `https://api-prod01.conferdeploy.net`. Once you're done, click the `Update Configuration` button.

![screenshot 2](/demo_screenshots/settings_page.png)

If you also noticed, there is a `Giphy API` section on the `Settings` page! :metal:	 With this, the "Random Gif Of The Day (GOTD)" section will have random gifs generated everytime you access the homepage, or everytime you click on the refresh button on the corner of the module. All you need to do is create an account in Giphy and then generate an API key so that you can provide it to CB Bot. Remember, with gifs come great responsibility, so at the moment everything is set to rated `PG-13` (Feel free to change this setting, but beware of the content!).

# Usage
This should be pretty self explanatory. However, check out www.allthingsdfir.com for some tips and tricks on how to use CB Bot. I've created a list of generic sweeps for you to start using. However, feel free to create new ones, and if you're open to sharing, don't hesitate to reach out to me and we can get it added to the config files!
