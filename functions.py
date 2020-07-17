import time, os, sys, re, datetime
import json, shouter, shell, subprocess
import pprint, random
from django.conf import settings
from django.core.mail import send_mail
import local_settings
MONTH2NUM = {'Aug': 8, 'Jul': 7, 'Apr': 4, 'Jun': 6, 'Oct': 10, 'May': 5, 'Jan': 1, 'Sep': 9, 'Feb': 2, 'Mar': 3, 'Nov': 11, 'Dec': 12}
migration_top = os.path.abspath(os.path.join(settings.BASE_DIR,"..","migration"))
NODE_NAME = os.uname().nodename

try:
	COMPONENT_STREAM_EXCLUDES = local_settings.COMPONENT_STREAM_EXCLUDES
except Exception as e:
	COMPONENT_STREAM_EXCLUDES = []

db = settings.DATABASES
scmcommand = local_settings.SCMCOMMAND
if not scmcommand:
	scmcommand = 'lscm'
try:
	MAIL_FROM = settings.MAIL_FROM
except Exception as e:
	MAIL_FROM = 'yourid@mail.com'
try:
	MAIL_ADMIN = settings.MAIL_ADMIN
except Exception as e:
	MAIL_ADMIN = ['yourid@mail.com']
if re.match(r'^yourid',MAIL_FROM):
	raise ValueError("\t!!! please set your email setting MAIL_FROM in local_settings.py")
if not MAIL_ADMIN or type(MAIL_ADMIN) != type([]) or re.match(r'^yourid',MAIL_ADMIN[0]):
	raise ValueError("\t!!! please set your email setting MAIL_ADMIN in local_settings.py")

def git_initialize(gitdir):
	os.makedirs(gitdir)
	os.chdir(gitdir)
	shouter.shout("Initialize git @%s" % gitdir)
	shell.execute("git init --bare")

def git_last_commitid(rtcdir='.'):
	return shell.getoutput("git -C %s log -1 --pretty=oneline" % rtcdir,clean=False).strip().split()[0]

def git_list_tags(rtcdir):
	return shell.getoutput("git -C %s tag" % rtcdir ,clean=False).strip().split('\n')

def notify_admin(subject='notify_subject from %s' % NODE_NAME, body='', mail_from=MAIL_FROM, mail_to=MAIL_ADMIN):
	try:
		send_mail(subject, body, mail_from, mail_to)
	except Exception as e:
		shouter.shout("\t.!. you did not configure mail properly, displaying it on screen")
		print(subject)
		print(body)

def git_got_changes(gitdir=None, logical=True):
	if not gitdir:
		gitdir = '.'
	output = shell.getoutput("git -C %s status -s" % gitdir,clean=False)
	if not logical:
		return output.strip()
	return output and output.strip() 

def git_compress_changeset(workspace=None,rtcdir='',changeset=None):
	from rtc.models import GitCommit, Author
	if changeset and workspace and rtcdir:
		author = changeset.author
		if not author:
			author,created = Author.objects.get_or_create(name='none',mail='none@xx.ibm.com',uuid='uuidforauthornone',userid='none@xx.ibm.com')
		shell.execute('%s' % author.git_config())
		command = 'env GIT_COMMITTER_DATE=%s git -C %s commit -m %s --date=%s' % (shell.quote(changeset.createtime.isoformat()), rtcdir, shell.quote(changeset.comment_with_workitem()), shell.quote(changeset.createtime.isoformat()))
		if os.path.exists(rtcdir):
			os.chdir(rtcdir)
			issues_conflicts = os.path.join(rtcdir,".issues","conflicts")
			with open(issues_conflicts,'a') as issue:
				issue.write("%s@%g\t\t%s\t\tcompress\t%s\n" % (changeset.uuid, changeset.level, workspace.stream.name, changeset.comment))
			out_status = shell.getoutput("git -C %s status -s" % rtcdir,clean=False)
			out_add = shell.getoutput("git -C %s add -A; git -C %s status -s" % (rtcdir, rtcdir), clean=False)
			out_commit = shell.getoutput(command,clean=False) 
			print(out_commit)
			out_log = shell.getoutput("git -C %s log -1 --pretty=oneline" % rtcdir,clean=False)
			print(out_log)
			commitid = out_log.split()[0]
			gitcommit,created = GitCommit.objects.get_or_create(commitid=commitid)
			if not created:
				shouter.shout("!!! got a previously created git commit, invest it")
				sys.exit(11)
			changeset.out_resume = "shortcut: compressed"
			changeset.out_load = "shortcut: compressed"
			gitcommit.out_status = out_status
			gitcommit.out_add = out_add
			gitcommit.out_commit = out_commit
			gitcommit.save()
			changeset.commit = gitcommit
			changeset.compressed = True
			changeset.migrated = True
			changeset.save()
			shouter.shout("\t... compressed changeset %s\t%g" % (changeset.uuid, changeset.level))

def rtc_initialize(rtcdir,gitdir=None,workspace=None,component=None,load=False,is_master=False,verifying=False):
	randint = random.randint(100,999)
	from rtc.models import GitCommit, ChangeSet, Author
	if not os.path.exists(rtcdir):
		shell.execute("mkdir -p %s ; rm -fr %s" % (rtcdir,rtcdir))
		shouter.shout("clone from git repo @%s to %s" % (gitdir, rtcdir))
		if is_master:
			shell.execute("git clone %s %s; sync" % (gitdir, rtcdir))
			os.makedirs(os.path.join(rtcdir,".issues"))
			with open(os.path.join(rtcdir,".issues","readme"),'w') as readme:
				readme.writelines("this folder record the issues of migration from rtc to git\n")
			shouter.shout("Create .gitignore")
			with open(os.path.join(rtcdir,".gitignore"), "w") as ignore:
				ignore.writelines(".jazz5\n.metadata\n.jazzShed\ncore*dmp\nSnap*rtc\nheapdump*phd\njavacore*txt\n")
			with open(os.path.join(rtcdir,".gitattributes"), "w") as gitattribute:
				gitattribute.writelines("* text=auto\n\n*.c text\n*.cpp text\n*.h text\n*.java text\n*.py text\n\n*.svg binary\n*.png binary\n*.jpg binary\n*.gif binary\n*.rpm binary\n*.jar binary\n*.tar binary\n*.tar.gz binary\n*.Z binary\n")
			shell.execute("git -C %s add -A" % rtcdir)
			changeset0 = ChangeSet.objects.all()[0]
			items = rtc_show_history(workspace=workspace,component=component,maxitems=1)
			if not 'changes' in items.keys() or len(items['changes']) != 1 or items['changes'][0]['uuid'] != changeset0.uuid:
				shouter.shout("\t!!! got incorrect initializing, inspect it manually please")
				sys.exit(9)
			item = items['changes'][0]
			author = item['author']
			timestamp = string2datetime(item["modified"])
			if not author in settings.COMPONENT_CREATORS.keys():
				try:
					author_instance = Author.objects.get(name=author)
					shell.execute('%s' % author_instance.git_config())
				except Exception as e:
					shouter.shout("\t.!.you did update your local_settings to provide who (%s) created the components" % author)
					shouter.shout("\t.!.use email address unknown@email.com instead")
					shell.execute('git config --replace-all user.name "%s" ; git config --replace-all user.email "%s"' % (author, 'unknown@email.com'))
			else:
				shell.execute('git config --replace-all user.name "%s" ; git config --replace-all user.email "%s"' % (author, settings.COMPONENT_CREATORS[author]))
			shell.execute("env GIT_COMMITTER_DATE=%s git -C %s commit -m \"%s\" --date %s" % (shell.quote(timestamp.isoformat()), rtcdir,item['comment'],shell.quote(timestamp.isoformat())))
			shell.execute("git -C %s push origin master:refs/heads/%s" % (rtcdir,re.sub(r' ', '', workspace.stream.name)))
			commitid = git_last_commitid(rtcdir=rtcdir)
			if not commitid:
				shouter.shout("got empty git commit id, exiting")
				sys.exit(9)
			gitcommit = GitCommit(commitid=commitid,timestamp=timestamp)
			gitcommit.save()
			changeset0.commit = gitcommit
			changeset0.migrated = True
			changeset0.save()
			shell.execute("rm -fr %s" % rtcdir)
	#	else:
	#		shouter.shout("\t!!! you need migrate your base stream first")
	#		sys.exit(5)
	shell.execute("git clone -b %s %s %s; sync" % (re.sub(r' ','',workspace.stream.name), gitdir, rtcdir))
	os.chdir(rtcdir)
	if load:
		shouter.shout("\t... load initial workspace")
		shell.execute("mv %s/.git %s/../.git-%g; sync" % (rtcdir, rtcdir, randint))
		workspace.ws_load(load_dir=rtcdir)
		time.sleep(10)
		shell.execute("mv %s/../.git-%g %s/.git ; sync ; git -C %s add -A" % (rtcdir, randint, rtcdir, rtcdir))
#	if not is_master:
#		changesets = list(workspace.stream.lastchangeset.get_ancestors().filter(migrated=False))
#		workspace.ws_suspend(rtcdir=rtcdir, changesets=changesets)
	shell.execute("git config push.default current")
	if not verifying:
		try:
			commitid = git_last_commitid(rtcdir=rtcdir)
			shouter.shout("\t... verify the last commit %s" % commitid)
			gitcommit = GitCommit.objects.get(commitid=commitid)
			if gitcommit.changeset:
				lastchangeset = gitcommit.changeset
				if lastchangeset.migrated:
					for cs in lastchangeset.children.all():
						print(cs)
						if cs in workspace.stream.lastchangeset.get_ancestors():
							shouter.shout("\t... verify that the stream migration is never started yet")
							if cs.migrated:
								shout("\t!!! got issue to migrate, certain changesets are migrated, manual check please")
								sys.exit(9)
				else:
					shout("\t!!! got issue to migrate, probably the parent branch is not migrated yet")
					sys.exit(9)
			else:
				shouter.shout("\t!!! database not clean, suppose each git commit corresponds to a changeset")
				sys.exit(9)
		except subprocess.CalledProcessError:
			shouter.shout("!!! what happen initializing rtc")
			sys.exit(9)
		except GitCommit.DoesNotExist:
			shouter.shout(".!.do not have this record yet")
			input("press enter to continue or ctrl+c to break")
	else:
		shouter.shout("\t... bypassing initial check since you are verifying stream/branch anyway")
		
def string2datetime(timestring):
	tsmatch = re.match("^(\d+)-(\w+)-(\d+)\s+(\d+):(\d+)\s+([ap]m)$", timestring.strip(), re.I)
	if tsmatch:
		tstuple = tsmatch.groups()
		if tstuple[5].upper() == "AM":
			return datetime.datetime(int(tstuple[2]),MONTH2NUM[tstuple[1]],int(tstuple[0]),int(tstuple[3]), int(tstuple[4]))
		elif tstuple[5].upper() == "PM":
			return datetime.datetime(int(tstuple[2]),MONTH2NUM[tstuple[1]],int(tstuple[0]),int(tstuple[3]) % 12 + 12, int(tstuple[4]))
		else:
			raise ValueError("Error converting timestring to datetime")
	tsmatchm = re.match("^(\d+)-(\w+)-(\d+)\s+(\d+):(\d+):(\d+)\s+([ap]m$)", timestring.strip(), re.I)
	if tsmatchm:
		tstuple = tsmatchm.groups()
		if tstuple[6].upper() == "AM":
			return datetime.datetime(int(tstuple[2]),MONTH2NUM[tstuple[1]],int(tstuple[0]),int(tstuple[3]), int(tstuple[4]), int(tstuple[5]))
		elif tstuple[6].upper() == "PM":
			return datetime.datetime(int(tstuple[2]),MONTH2NUM[tstuple[1]],int(tstuple[0]),int(tstuple[3]) % 12 + 12, int(tstuple[4]), int(tstuple[5]))
		else:
			raise ValueError("Error converting timestring to datetime")
	tsmatchm = re.match("^(\w+)\s+(\d+),\s+(\d+)\s+(\d+):(\d+)\s+([ap]m$)", timestring.strip(), re.I)
	if tsmatchm:
		tstuple = tsmatchm.groups()
		if tstuple[5].upper() == "AM":
			return datetime.datetime(int(tstuple[2]),MONTH2NUM[tstuple[0]],int(tstuple[1]),int(tstuple[3]), int(tstuple[4]))
		elif tstuple[5].upper() == "PM":
			return datetime.datetime(int(tstuple[2]),MONTH2NUM[tstuple[0]],int(tstuple[1]),int(tstuple[3]) % 12 + 12, int(tstuple[4]))
		else:
			raise ValueError("Error converting timestring to datetime")
	tsmatchm = re.match("^(\w+)\s+(\d+),\s+(\d+)\s+(\d+):(\d+):(\d+)\s+([ap]m$)", timestring.strip(), re.I)
	if tsmatchm:
		tstuple = tsmatchm.groups()
		if tstuple[6].upper() == "AM":
			return datetime.datetime(int(tstuple[2]),MONTH2NUM[tstuple[0]],int(tstuple[1]),int(tstuple[3]), int(tstuple[4]), int(tstuple[5]))
		elif tstuple[6].upper() == "PM":
			return datetime.datetime(int(tstuple[2]),MONTH2NUM[tstuple[0]],int(tstuple[1]),int(tstuple[3]) % 12 + 12, int(tstuple[4]), int(tstuple[5]))
		else:
			raise ValueError("Error converting timestring to datetime")
	tsmatchm = re.match(r'^(\d+)-(\d+)-(\d+)\s+(\d+):(\d+):(\d+)$', timestring.strip())
	if tsmatchm:
		tstuple = tsmatchm.groups()
		return datetime.datetime(int(tstuple[0]),int(tstuple[1]),int(tstuple[2]),int(tstuple[3]),int(tstuple[4]),int(tstuple[5]))
	tsmatchm = re.match(r'^(\d+)/(\d+)/(\d+)$', timestring.strip(), re.I)
	if tsmatchm:
		tstuple = tsmatchm.groups()
		return datetime.datetime(int(tstuple[0]),int(tstuple[1]),int(tstuple[2]))
	shouter.shout("\t!!!error tranform %s to datetime" % timestring.strip())
	raise ValueError("Error converting timestring to datetime")
	
def rtclogin(real_login=False):
	login_command0 = "%s login -r https://jazz_repo/url -u your_user -P yourpassword -n rtc -c" % scmcommand
	login_command = login_command0
	if local_settings.rtc_url and local_settings.rtc_user and local_settings.rtc_pass:
		login_command = "%s login -r %s -u %s -P %s -n rtc -c" % (scmcommand, local_settings.rtc_url, local_settings.rtc_user, local_settings.rtc_pass)
	if real_login:
		if login_command != login_command0:
			shell.execute(login_command)
		else:
			shouter.shout(login_command0)

		#shell.execute("%s login -n rtc -c" % scmcommand)
	shouter.shout("checking for cached rtc connections")
	while not re.match('.*, rtc,', subprocess.check_output("%s list connections" % scmcommand, shell=True).decode()):
		if login_command != login_command0:
			shell.execute(login_command)
		else:
			shouter.shout("syntax: %s" % login_command0)
			input("hit any key to continue when you did the login, or better break and update local_settings.py to rtc information")
	shouter.shout("\t... found cached connections")

def rtclogin_restart():
	shouter.shout("\t.!. restarting lscm service")
	shell.execute("lscm logout -r rtc")
	shell.execute("scm daemon stop -a")
	time.sleep(60)
	shell.execute("rm -f javacore*txt heapdump*phd Snap*trc core*dmp; exit 0")
	rtclogin(real_login=True)
	time.sleep(5)

def rtc_show_history(workspace=None, component=None, maxitems=1):
	if not component:
		if workspace.component:
			component = workspace.component
		elif workspace.stream and workspace.stream.component:
			componnt = workspace.stream.component
		else:
			shouter.shout("\t.!. can not figure out the component to show history for")
			raise ValueError("Component info not available")
	command = "%s show history -r rtc -w %s -m %g -j -C %s" % (scmcommand, workspace.uuid, maxitems, component.uuid)
	try:
		return json.loads(shell.getoutput(command,clean=False))
	except subprocess.CalledProcessError as lscmservice:
		if lscmservice.returncode == 3:
			shouter.shout("\t.!. got return code 3, sleep some time to get the locks back")
			rtclogin_restart()
			time.sleep(5)
			return json.loads(shell.getoutput(command,clean=False))
		else:
			raise ValueError("\t!!!show history returned error code %g" % lscmservice.returncode)
		
def sync_project():
	from rtc.models import Stream, ProjectArea
	output = shell.getoutput("%s list projectareas -r rtc -j" % scmcommand,clean=False)
	if output:
		projects = json.loads(output)
		for project in projects:
			if 'name' in project.keys() and 'uuid' in project.keys():
				shouter.shout("\t refresh projectarea %s" % project['name'])
				ProjectArea.objects.get_or_create(name=project['name'],uuid=project['uuid'])

def sync_streams(short_cut=False,component_name=''):
	from rtc.models import Stream, ProjectArea, Component
	shouter.shout("\tCollecting Streams and their components")
	# shen added some comments
	# short_cut=False only in options.infoinit
	if short_cut:
		shouter.shout("\t.!.Assume you have loaded the fixtures or you are repeating inforupdate")
		shouter.shout("\t...bypassing stream creation and its components updates, simply resetting stream.component instead")
		try:
			# shen added some comments
			# exclude bad or unwanted streams defined in local_settings.py for a given compoment
			excluded_stream_names = []
			if component_name in COMPONENT_STREAM_EXCLUDES.keys():
				excluded_stream_names = COMPONENT_STREAM_EXCLUDES[component_name]
			component = Component.objects.get(name=component_name)
			# shen added some comments
			#looping throght all streams, add the given component with component_name into the streams
			for stream in Stream.objects.all():
				if component in stream.components.all():
					if stream.name not in excluded_stream_names:
						if stream.component != component:
							shouter.shout("\t...setting componet %s for stream %s" % (component_name, stream.name))
							stream.component = component
							stream.save()
					else:
						if stream.component and stream.component == component:
							shouter.shout("\t.!.unsetting component %s for stream %s" % (component_name, stream.name))
							stream.component = None
							stream.save()
				else:
					if stream.component and stream.component == component:
						shouter.shout("\t.!.unsetting component %s for stream %s" % (component_name, stream.name))
						stream.component = None
						stream.save()
			shouter.shout("Streams that has component %s are:" % component_name)
			for stream in Stream.objects.filter(component__name=component_name):
				print("%-8g%s" % (stream.id, stream.name))
		except Component.DoesNotExist:
			raise ValueError("\t!!!The component name you specified was not found, did you run --infoinit?")
	else:
		# shen added some comments
		# in the case of ---infoinit
		# looping RTC project areas and collecte all streams, initialized stream and compoment DB objects 
		for projectarea in ProjectArea.objects.all():
			shouter.shout("\t ... inside project area %s" % projectarea.name)
			output = shell.getoutput("%s list streams -r rtc --projectarea %s  -m 512 -j" % (scmcommand, projectarea.uuid), clean=False)
			items = json.loads(output)
			#pprint.pprint(items)
			for item in items:
				if 'name' in item.keys() and 'uuid' in item.keys():
					shouter.shout("\t\t ... handling %s(%s)" % (item['uuid'], item['name']))
					stream,created = Stream.objects.get_or_create(uuid=item['uuid'])
					if created:
						stream.name = item['name']
						stream.project = projectarea
						stream.save()
						output = shell.getoutput("%s list components -r rtc  %s -j" % (scmcommand, stream.uuid), clean=False)
						components = json.loads(output)
						for component_info in components['workspaces'][0]['components']:
							if 'name' in component_info.keys() and 'uuid' in component_info.keys():
								component,created = Component.objects.get_or_create(uuid=component_info['uuid'])
								stream.components.add(component)
								if created:
									component.name = component_info['name']
									component.save()
								if component.name != component_info['name']:
									shouter.shout("\t!!!got inconsistent component %s(%s)" % (component_info['uuid'],component_info['name']))
									input("any key to continue or break")
				else:
					shouter.shout("\t!!! unknown stream met")
					pprint.pprint(item)


def save_compress_changesets_to_json(json_path, compress_changesets):
	# save compress_changesets to a json file
	if not os.path.exists(os.path.dirname(json_path)):
		os.makedirs(os.path.dirname(json_path))
	# shen added to show fewer "persist compressed_changesets" messages
	if os.path.isfile(json_path) and os.path.getsize(json_path) == 2 and not compress_changesets:
		return
	with open(json_path,'w') as f:
		print("... persist compressed_changesets")
		json.dump(compress_changesets,f)
