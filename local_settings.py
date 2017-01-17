import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
## rtc login information
rtc_url = ''
rtc_user = ''
rtc_pass = ''
## when reporting, show # of changesets before and after for each stream
levelinterval = 10
## when reporting, show this range of changesets for each stream
levelrange = []
## only handle subset of streams, [] indicated to handle all
streams = []

## email settings
MAIL_FROM = 'yourid@mail.com'
MAIL_ADMIN = ['yourid@mail.com',]
EMAIL_HOST = 'localhost'
EMAIL_PORT = 25
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False
EMAIL_SSL_CERTFILE = None
EMAIL_SSL_KEYFILE = None

## command used for rtc querys
SCMCOMMAND = 'lscm'

## use history file got from gui for needed streams
USE_HISTORY_FILE = True

## do stream based migration
STREAM_BASED = True

## set some limits so that we constantly push to git repository and force load rtc workspaces
PUSHLIMIT = 50
FORCELOAD = 100

## update this to provide intial creator information
COMPONENT_CREATORS = {
	"user name 1": 'user1@mail.com', # who created the component 1
	"user name 2": 'user2@mail.com', # who created the component 2
	"user name 3": 'user3@mail.com', # who created the component 3
}

## aggressively squash changesets that created previous than deliver time
## if aggresive, it squashes regarding to the changeset creation time only, this will produce more squashes but fast
## normally, try to accept / discard cycle and this will reduce squashes.
CHANGESET_SQUASH_POLICY_AGGRESIVE = False
CHANGESET_SQUASH_TRY_BEST_LIMIT = 10

DATABASES = {
    'default': {
	'ENGINE': 'django.db.backends.sqlite3',
	'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
	},
#    'default': {
#	'ENGINE': 'django.db.backends.mysql',
#	'NAME': 'utopia',
#	'CONN_MAX_AGE': 10800,
#	'HOST': 'localhost',
#	'USER': 'root',
#	'PASSWORD': '',
#	'PORT': '',
#	}
}

