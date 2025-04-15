import re
import os
from os import environ
from Script import script

id_pattern = re.compile(r'^.\d+$')
def is_enabled(value, default):
    if value.lower() in ["true", "yes", "1", "enable", "y"]:
        return True
    elif value.lower() in ["false", "no", "0", "disable", "n"]:
        return False
    else:
        return default

# Bot Information
API_ID = int(environ.get("API_ID", "26205215"))
API_HASH = environ.get("API_HASH", "d4d9b7bce6d76bec759e404ecf2c3ebf")
BOT_TOKEN = environ.get("BOT_TOKEN", "7235447334:AAFZ4rBUNV6wsD2hvMB3zXxlU7M9GFj7dGM")

PICS = (environ.get('PICS', 'https://freeimage.host/i/d10VHep')).split() # Bot Start Picture
ADMINS = [int(admin) if id_pattern.search(admin) else admin for admin in environ.get('ADMINS', '1178233430').split()]
BOT_USERNAME = environ.get("BOT_USERNAME", "R3volutionary_Bot") # without @
PORT = environ.get("PORT", "8080")

# Clone Info :-
CLONE_MODE = bool(environ.get('CLONE_MODE', True)) # Set True or False
# If Clone Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
CLONE_DB_URI = environ.get("CLONE_DB_URI", "mongodb+srv://ZahidNazir:ZahidNazir@1stcluster.1p0dlne.mongodb.net/?retryWrites=true&w=majority&appName=1stcluster")
CDB_NAME = environ.get("CDB_NAME", "cloned-bots")

# Database Information
DB_URI = environ.get("DB_URI", "mongodb+srv://ZahidNazir:ZahidNazir@1stcluster.1p0dlne.mongodb.net/?retryWrites=true&w=majority&appName=1stcluster")
DB_NAME = environ.get("DB_NAME", "Courses")

# Auto Delete Information
AUTO_DELETE_MODE = bool(environ.get('AUTO_DELETE_MODE', True)) # Set True or False

# If Auto Delete Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
AUTO_DELETE = int(environ.get("AUTO_DELETE", "2")) # Time in Minutes
AUTO_DELETE_TIME = int(environ.get("AUTO_DELETE_TIME", "120")) # Time in Seconds

# dedicated database channel's chat id for storing file data
# Replace with your dedicated database channel's chat id
DB_CHANNEL = int(environ.get("DB_CHANNEL", "-1002225127966"))

# Bot uptime information and stats are shown reply add by tactition
BOT_STATS_TEXT = "<b>BOT UPTIME</b>\n{uptime}"
AUTH_CHANNEL = [int(ch) if id_pattern.search(ch) else ch for ch in environ.get('AUTH_CHANNEL', '-1002183158596').split()]
USER_REPLY_TEXT = "❌Don't send me messages! You Can't Use Me Unless You Have The Special Link To Access My Content."

BOT_ID = int(environ.get("BOT_ID", "7235447334")) # bot id from https://api.telegram.org/bot<YourBotToken>/getMe
QUOTE_CHANNEL = int(environ.get("QUOTE_CHANNEL" ,"-1002598222123"))  # replace with your actual quotes channel ID
QUOTE_DELETE_DELAY = int(os.environ.get("QUOTE_DELETE_DELAY", "14400"))  # delay in seconds
DELETION_INTERVAL = float(os.environ.get("DELETION_INTERVAL", "1"))  # seconds between scheduling each deletion task means how many seconds wait should be there to delete the message in bot pm
ARTICLE_CHANNEL = int(environ.get("QUOTE_CHANNEL" ,"-1002583776397"))  # replace with your actual quotes channel ID
FACTS_CHANNEL = int(environ.get("QUOTE_CHANNEL" ,"-1002625104089"))  # replace with your actual Facts channel ID

# Channel Information
LOG_CHANNEL = int(environ.get("LOG_CHANNEL", "-1002230949609"))

# File Caption Information
CUSTOM_FILE_CAPTION = environ.get("CUSTOM_FILE_CAPTION", f"{script.CAPTION}")
BATCH_FILE_CAPTION = environ.get("BATCH_FILE_CAPTION", CUSTOM_FILE_CAPTION)

# Enable - True or Disable - False
PUBLIC_FILE_STORE = is_enabled((environ.get('PUBLIC_FILE_STORE', "False")), False)

# Verify Info :-
VERIFY_MODE = bool(environ.get('VERIFY_MODE', False)) # Set True or False

# If Verify Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
SHORTLINK_URL = environ.get("SHORTLINK_URL", "techvjlink.site") # shortlink domain without https://
SHORTLINK_API = environ.get("SHORTLINK_API", "bae78dac0bb760b134dae18985199865614c5778") # shortlink api
VERIFY_TUTORIAL = environ.get("VERIFY_TUTORIAL", "") # how to open link 

# Website Info:
WEBSITE_URL_MODE = bool(environ.get('WEBSITE_URL_MODE', False)) # Set True or False

# If Website Url Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
WEBSITE_URL = environ.get("WEBSITE_URL", "https://webassetsblog.infinityfreeapp.com/telegram-bot/") # For More Information Check Video On Yt -

# File Stream Config
STREAM_MODE = bool(environ.get('STREAM_MODE', True)) # Set True or False

# If Stream Mode Is True Then Fill All Required Variable, If False Then Don't Fill.
MULTI_CLIENT = True
SLEEP_THRESHOLD = int(environ.get('SLEEP_THRESHOLD', '00'))
PING_INTERVAL = int(environ.get("PING_INTERVAL", "40")) # in Seconds 
if 'DYNO' in environ:
    ON_HEROKU = True
else:
    ON_HEROKU = False
URL = environ.get("URL", "")
