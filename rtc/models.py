from django.db import models

from django.conf import settings
from mptt.models import  MPTTModel, TreeForeignKey
import os, re, json, shouter, shell, pprint, time
from functions import *
import re

USE_HISTORY_FILE = settings.USE_HISTORY_FILE
if not USE_HISTORY_FILE:
	USE_HISTORY_FILE = True
PUSHLIMIT = settings.PUSHLIMIT
if not PUSHLIMIT:
	PUSHLIMIT = 50
FORCELOAD = settings.FORCELOAD
if not FORCELOAD:
	FORCELOAD = 100
try:
	SQUASH_AGGRESIVE = settings.CHANGESET_SQUASH_POLICY_AGGRESIVE
except Exception as e:
	SQUASH_AGGRESIVE = False
try:
	SQUASH_MAX_TRY = settings.CHANGESET_SQUASH_TRY_BEST_LIMIT
except Exception as e:
	SQUASH_MAX_TRY = 10
if SQUASH_MAX_TRY > 10:
	SQUASH_MAX_TRY = 10
try:
	RTC_DISPLAY_NAME_IN_HISTORY = settings.RTC_DISPLAY_NAME_IN_HISTORY
except Exception as e:
	RTC_DISPLAY_NAME_IN_HISTORY = 'RTC'

# Create your models here.
class Category(models.Model):
	name = models.CharField(max_length=16,unique=True)
	def __str__(self):
		return self.name

class WorkitemType(models.Model):
	name = models.CharField(max_length=64,unique=True)
	def __str__(self):
		return self.name

class Contributor(models.Model):
	name = models.CharField(max_length=32,unique=True)
	def __str__(self):
		return self.name

class Author(models.Model):
	name = models.CharField(max_length=32)
	mail = models.CharField(max_length=64)
	userid = models.CharField(max_length=64)
	uuid = models.CharField(max_length=64,unique=True)

	def __str__(self):
		return self.name + "(" + self.uuid + ")"

	def git_config(self):
		git_config_user = "unknown"
		git_config_email = "unknown@xx.ibm.com"
		if self.mail:
			git_config_email = self.mail
		if self.name:
			git_config_user = self.name
		return 'git config --replace-all user.name "%s" ; git config --replace-all user.email "%s"' % (git_config_user, git_config_email)

class Workitem(MPTTModel):
	number = models.IntegerField()
	label = models.TextField(default='')
	uuid = models.CharField(max_length=64,unique=True)
	type = models.ForeignKey(WorkitemType,null=True,blank=True,default=None,on_delete=models.SET_NULL)
	parent = TreeForeignKey('self',null=True,blank=True,related_name='children',on_delete=models.SET_NULL)
	displayed = models.BooleanField(default=False,editable=False)
	def __str__(self):
		return str(self.number) + ": " + self.uuid + "(" + self.label + ")"

class ProjectArea(models.Model):
	name = models.CharField(max_length=255,unique=True)
	uuid = models.CharField(max_length=64,unique=True)
	def __str__(self):
		return self.name + " (" + self.uuid + ")"
	def sync_streams(self,keyword="component_branch"):
		shouter.shout("\tCollecting Streams for projectarea %s with uuid %s" % (self.name, self.uuid))
		output = shell.getoutput("%s list streams -r rtc --projectarea %s -m 2000 -j -n %s" % (scmcommand, self.name, re.sub(r'_.*','',keyword)), clean=False)
		items = json.loads(output)
		for item in items:
			if item['name'] and item['uuid']:
				if re.match(keyword,item['name']):
					Stream.objects.get_or_create(name=item['name'],uuid=item['uuid'],project=self)

class GitCommit(models.Model):
	commitid = models.CharField(max_length=128,default='commitid',unique=True)
	timestamp = models.DateTimeField(default=datetime.datetime.now)
	out_status = models.TextField(default='')
	out_add = models.TextField(default='')
	out_commit = models.TextField(default='')
	class Meta:
		ordering = ["-timestamp"]
	def __str__(self):
		return self.commitid
		
	
class ChangeSet(MPTTModel):
	uuid = models.CharField(max_length=64)
	sequence = models.IntegerField(default=1)
	comment = models.TextField(default="")
	author = models.ForeignKey(Author,null=True)
	workitems = models.ManyToManyField(Workitem)
	category = models.ForeignKey(Category,default=1)
	migrated = models.BooleanField(default=False)
	compared = models.BooleanField(default=False)
	compressed = models.BooleanField(default=False)
	showstopper = models.BooleanField(default=False)
	#commit = models.ForeignKey(GitCommit,null=True,on_delete=models.SET_NULL)
	commit = models.OneToOneField(GitCommit,null=True,on_delete=models.SET_NULL)
	parent = TreeForeignKey('self',verbose_name='following',null=True,blank=True,related_name='children')
	created = models.CharField(max_length=64,default='')
	createtime = models.DateTimeField(blank=True,null=True,default=None)
	delivered = models.CharField(max_length=64,default='')
	delivertime = models.DateTimeField(blank=True,null=True,default=None)
	out_resume = models.TextField(default='')
	out_load = models.TextField(default='')
	out_verify = models.TextField(default='')

	class Meta:
		unique_together = ('uuid','sequence')
	def __str__(self):
		return self.uuid

	def comment_with_workitem(self):
		wiinfo = ''
		if self.workitems.all():
			wiinfo += "WI %g: " % self.workitems.order_by('-number')[0].number
		#	for workitem in self.workitems.all():
		#		wiinfo += str(workitem.number) + ", "
		#	wiinfo = re.sub(r', $',': ',wiinfo)
		return wiinfo + self.comment

	def resume(self,workspace,use_accept=False,manual=False,flagconflict=False,on_conflict='resolve',rtcdir='',compress_changesets=[],timestamp=None,checkpoint=False):
		if not rtcdir:
			shouter.shout("\t!!! you did not specify rtcdir")
			sys.exit(9)
		if compress_changesets:
			shouter.shout("\t.!. changesets compress happens, attention %s" % compress_changesets)
		os.chdir(rtcdir)
		if manual:
			shouter.shout("\t...manual resuming %s" % self.comment_with_workitem())
			out_status = shell.getoutput("git -C %s status -s" % rtcdir,clean=False)
			author = self.author
			if not author:
				author,created = Author.objects.get_or_create(name='none',mail='none@xx.ibm.com',uuid='uuidforauthornone',userid='none@xx.ibm.com')
			shell.execute('%s' % author.git_config()) 
			out_add = shell.getoutput("git -C %s add -A; git -C %s status -s" % (rtcdir, rtcdir), clean=False)
			print(out_add)
			command = 'env GIT_COMMITTER_DATE=%s git -C %s commit -m %s --date=%s' % (shell.quote(self.createtime.isoformat()), rtcdir, shell.quote(self.comment_with_workitem()), shell.quote(self.createtime.isoformat()))
			try:
				out_commit = shell.getoutput(command,clean=False) 
			except subprocess.CalledProcessError:
				shouter.shout("\t!!! got an issue commit code, here is the info, ctrl + c to break or any other key to continue")
				pprint.pprint(out_resume)
				print(out_add)
				print("--->>> logging this issue to .issues/commits")
				time.sleep(5)
				issues_commits = os.path.join(".issues","commits")
				with open(issues_commits,'a') as issue:
					issue.write("%s@%g\t\t%s\t\t%s\n" % (self.uuid, self.level, workspace.stream.name, self.comment))
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
			if flagconflict:
				issues_conflicts = os.path.join(".issues","conflicts")
				with open(issues_conflicts,'a') as issue:
					issue.write("%s@%g\t\t%s\t\t%s\n" % (self.uuid, self.level, workspace.stream.name, self.comment))
			self.out_resume = "manual handle"
			self.out_load = "manual handle"
			gitcommit.out_status = out_status
			gitcommit.out_add = out_add
			gitcommit.out_commit = out_commit
			gitcommit.save()
			self.commit = gitcommit
			self.migrated = True
			self.save()
			return True
		if not self.migrated:
			out_load = ''
			out_resume = ''
			if self.showstopper:
				notify_admin(subject="Got Conflict for Changeset Migration",body=self.uuid + " : " + self.comment_with_workitem())
				raise ValueError("Manual process please!")
			if self.is_root_node():
				shouter.shout(".!.bypassing root node changeset %s: %s" % (self.uuid,self.comment))
			elif self.category.name != 'changeset':
				shouter.shout(".!.bypassing non-changeset changeset %s: %s" % (self.uuid,self.comment))
				answer = input("type ctrl+c to break, else to continue")
			elif not self.comment or not self.createtime:
				shouter.shout(".!.got strange changeset: no comment or createtime for %s" % self.uuid)
				answer = input("type ctrl+c to break, else to continue")
			else:
				flagconflict = False
				shouter.shout("\t...resuming %s" % self.comment_with_workitem())
				if use_accept:
					#command = "%s accept -c -r rtc --accept-missing-changesets -q -t %s --no-merge -j -o %s" % (scmcommand, workspace.name, self.uuid)
					command = "%s accept -c -r rtc -t %s --no-merge -j -o " % (scmcommand, workspace.name)
				else:
					#command = "%s resume changeset %s -r rtc -t %s --no-merge --resume-missing-changesets -j -o" % (scmcommand, self.uuid, workspace.name)
					command = "%s resume changeset -r rtc -t %s --no-merge -j -o " % (scmcommand, workspace.name)
				for cs in compress_changesets:
					changeset = self.get_ancestors().get(uuid=cs)
					if not changeset.migrated:
						shouter.shout("\t.!. mark changeset squash for changeset %g\t%s" % (changeset.level, changeset.uuid))
						if changeset.lastchangeset.all():
							bis_set = set()
							for bis in changeset.lastchangeset.all():
								bis_set.add(bis.baseline)
							shouter.shout("\t.!. changeset %s\t%g is on baseline %s, are you sure you wish to compress?" % (self.uuid, self.level, list(map(lambda baseline: baseline.name, bis_set))))
							input("continue or break?")
						git_compress_changeset(workspace=workspace,rtcdir=rtcdir,changeset=changeset)
					command += cs + " "
				command += self.uuid
				try:
					out_resume = shell.getoutput(command,clean=False)
					compress_changesets = []
					returncode = 0
				except subprocess.CalledProcessError as lscmservice:
					notify_admin(subject="attention lscm accept on %s" % NODE_NAME, body=self.uuid + " : " + self.comment_with_workitem())
					if lscmservice.returncode == 11:
						flagconflict = True
						shouter.shout("\t.!. got return code 11, got conflicts for resume")
						if on_conflict != 'resolve':
							self.showstopper = True
							self.save()
							notify_admin(subject="Got Conflict for Changeset Migration",body=self.uuid + " : " + self.comment_with_workitem())
							raise ValueError("Manual process please!")
						out_resume = lscmservice.output
						returncode = self.check_conflicts(compress_changesets=compress_changesets)
						if returncode == 0:
							compress_changesets = []
						elif returncode == 7:
							compress_changesets.append(self.uuid)
							self.compressed = True
							self.save()
#						shouter.shout("\t.!. try manual merge for conflict %s" % self.uuid)
						time.sleep(2)
						#workspace.ws_load(load_dir=rtcdir)
#						shouter.shout("\t... act in 10 seconds if you wish to break")
						print(shell.getoutput('lscm show status -i "in:cb out:c"; exit 0',clean=False))
#						time.sleep(2)
#						input("enter to continue or ctrl+c to abort")
#						shell.execute("lscm discard -r rtc %s" % self.uuid)
#						shell.execute("lscm resolve conflict -r rtc --auto-merge")
						workspace.ws_remove_conflict_merge(rtcdir=rtcdir,changeset=self)
					elif lscmservice.returncode == 3:
						shouter.shout("\t.!. got return code 3, sleep some time to get the locks back")
						rtclogin_restart()
						time.sleep(5)
						print(shell.getoutput("%s -u y -a n show history -r rtc -w %s -m 5 -C %s" % (scmcommand, workspace.name, workspace.component.name),clean=False))
						shell.getoutput("%s discard -r rtc -w %s -o %s" % (scmcommand, workspace.name, self.uuid),clean=False)
						time.sleep(10)
						workspace.ws_load(load_dir=rtcdir)
						time.sleep(5)
						if git_got_changes():
							shouter.shout("\t!!! local workspace not clean any more, manually handle please")
							sys.exit(9)
						else:
							shouter.shout("\t... local workspace clean after discard, retry resuming")
							out_resume = shell.getoutput(command,clean=False)
					elif lscmservice.returncode == 243:
						shouter.shout("\t... lscm service issue, restarting")
						rtclogin_restart()
						time.sleep(5)
						out_resume = shell.getoutput(command,clean=False)
					else:
						raise ValueError("!!! Got unexpected resume error, lscm returned %g" % lscmservice.returncode)
#				time.sleep(1)
				shell.execute("sync")
				if checkpoint:
					workspace.ws_remove_conflict_merge(rtcdir=rtcdir,changeset=self)
					time.sleep(2)
					workspace.ws_load(load_dir=rtcdir)
				if self.level % FORCELOAD == FORCELOAD - 1:
					shouter.shout("...... force load workspace for level %g" % self.level)
					time.sleep(2)
					workspace.ws_load(load_dir=rtcdir)
				elif not git_got_changes():
					shouter.shout("...... did not get change, try force load")
					if returncode != 7:
						time.sleep(2)
						workspace.ws_load(load_dir=rtcdir)
				else:
					shouter.shout("...... got changes automatically")
				out_status = shell.getoutput("git -C %s status -s" % rtcdir,clean=False)
				author = self.author
				if not author:
					author,created = Author.objects.get_or_create(name='none',mail='none@xx.ibm.com',uuid='uuidforauthornone',userid='none@xx.ibm.com')
				shell.execute('%s' % author.git_config()) 
				out_add = shell.getoutput("git -C %s add -A; git -C %s status -s" % (rtcdir, rtcdir), clean=False)
				print(out_add)
				command = 'env GIT_COMMITTER_DATE=%s git -C %s commit -m %s --date=%s' % (shell.quote(self.createtime.isoformat()), rtcdir, shell.quote(self.comment_with_workitem()), shell.quote(self.createtime.isoformat()))
				try:
					out_commit = shell.getoutput(command,clean=False) 
				except subprocess.CalledProcessError:
					shouter.shout("\t!!! got an issue commit code, here is the info, ctrl + c to break or any other key to continue")
					pprint.pprint(out_resume)
					print(out_add)
					print("--->>> logging this issue to .issues/commits")
					time.sleep(5)
					issues_commits = os.path.join(".issues","commits")
					with open(issues_commits,'a') as issue:
						issue.write("%s@%g\t\t%s\t\t%s\n" % (self.uuid, self.level, workspace.stream.name, self.comment))
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
				self.out_resume = out_resume
				self.out_load = out_load
				gitcommit.out_status = out_status
				gitcommit.out_add = out_add
				gitcommit.out_commit = out_commit
				gitcommit.save()
				self.commit = gitcommit
				self.migrated = True
				self.save()
				if flagconflict:
					issues_conflicts = os.path.join(".issues","conflicts")
					with open(issues_conflicts,'a') as issue:
						if returncode == 7:
							issue.write("%s@%g\t\t%s\t\tcompress\t%s\n" % (self.uuid, self.level, workspace.stream.name, self.comment))
						else:
							issue.write("%s@%g\t\t%s\t\t%s\n" % (self.uuid, self.level, workspace.stream.name, self.comment))
		else:
			shouter.shout("\t.!. changeset: %s has been migrated" % self.uuid)
		return compress_changesets
	def check_conflicts(self,compress_changesets=[]):
		try:
			output = shell.getoutput("lscm show conflicts -j",clean=False)
			if output:
				items = json.loads(output)
				if 'conflicts' in items.keys():
					for item in items['conflicts']:
						conflict,created = Conflict.objects.get_or_create(uuid=item['uuid'])
						if created:
							conflict.pathhint = item['path-hint']
							conflict.typeoutgoing = item['type-outgoing']
							conflict.typeproposed = item['type-proposed']
							conflict.json = output
							conflict.save()
						conflict.changesets.add(self)
						conflict.resolve()
				else:
					shouter.shout("\t.!. did not actually find conflict for %s" % self.uuid)
			return 0
		except subprocess.CalledProcessError as lscmservice:
			shouter.shout("\t.!. failed to show conflicts for changeset %s,return code %g" % (self.uuid, lscmservice.returncode))
			if lscmservice.returncode == 7:
				shouter.shout("\t.!! conflicts contains UNRESOLVED paths, discard and accept with the next changeset until unresoved gone")
				shouter.shout("\t... try to discard unresolved changesets")
				command = "%s discard -r rtc -o " % scmcommand
				for cs in  compress_changesets:
					command += cs + " "
				command += self.uuid
				shell.execute(command)
				shell.execute("%s status" % scmcommand)
				shell.execute("git status -s")
				return lscmservice.returncode
			else:
				input("\t.!!show conflict issue, continue or break?")
				raise ValueError("\t!!!manually check the accept and conflicts please")
				return 9999

class GitBranch(models.Model):
	name = models.CharField(max_length=128)
	branchpoint = models.ForeignKey(ChangeSet,null=True,on_delete=models.SET_NULL)
	def __str__(self):
		return self.name + '@' + self.branchpoint.commit.commitid

class Conflict(models.Model):
	uuid = models.CharField(max_length=64,unique=True)
	timestamp = models.DateTimeField(auto_now_add=True)
	pathhint = models.CharField(max_length=128,default='')
	typeoutgoing = models.CharField(max_length=32,default='')
	typeproposed = models.CharField(max_length=32,default='')
	changesets = models.ManyToManyField(ChangeSet)
	json = models.TextField(default='')
	class Meta:
		ordering = ["-timestamp"]
	def __str__(self):
		return self.uuid + ": " + self.pathhint
	def resolve(self):
		shell.execute("lscm resolve conflict --proposed %s" % self.uuid)
		time.sleep(1)
		
class Component(models.Model):
	uuid = models.CharField(max_length=64,unique=True)
	name = models.CharField(max_length=255,default='')
	category = models.ForeignKey(Category,default=2)
#	message = models.CharField(max_length=512,default="no message")
#	parent = TreeForeignKey('self',verbose_name='managed by',null=True,blank=True,related_name='children')
	def __str__(self):
		return self.name + " (component:" + self.uuid + ")"
	def update_baselines(self):
		items = json.loads(shell.getoutput("%s list baselines -C %s -r rtc -m 10000 -j" % (scmcommand, self.uuid), clean=False))
		for item in items:
			if type(item) == type({}) and 'baselines' in item.keys():
				for sitem in item['baselines']:
					if 'uuid' in sitem.keys() and 'id' in sitem.keys() and 'name' in sitem.keys() and 'contributor' in sitem.keys() and 'comment' in sitem.keys() and 'creationDate' in sitem.keys():
						contributor,created = Contributor.objects.get_or_create(name=sitem['contributor'])
						baseline,created = Baseline.objects.get_or_create(uuid=sitem['uuid'],component=self)
						if created:
							baseline.name = sitem['name']
							baseline.bid = int(sitem['id'])
							baseline.comment = sitem['comment']
							baseline.contributor = contributor
							baseline.created = sitem['creationDate']
							baseline.createtime = string2datetime(sitem['creationDate'])
							baseline.save()
						else:
							if baseline.name != sitem['name'] or baseline.comment != sitem['comment'] or baseline.component != self:
								shouter.shout("!!! found strange baseline for snapshot")
								raise ValueError("Found Strange baseline, check please")
					else:
						shouter.shout(".!. met incomplete baseline for component %s" % self.name)
						input("...... any key to continue or break")
				
class Baseline(MPTTModel):
	uuid = models.CharField(max_length=64,unique=True)
	bid = models.IntegerField(default=0)
	name = models.CharField(max_length=512)
	comment = models.CharField(max_length=1024,default='')
	category = models.ForeignKey(Category,default=4)
	created = models.CharField(max_length=64,default='')
	createtime = models.DateTimeField(blank=True,null=True,default=None)
	contributor = models.ForeignKey(Contributor,null=True,on_delete=models.SET_NULL)
	component = models.ForeignKey(Component)
	historys = models.ManyToManyField(ChangeSet,blank=True)
	historys_processed = models.BooleanField(default=False)
	lastchangeset = TreeForeignKey(ChangeSet,related_name="baselines_lastchangeset_set",blank=True,null=True,default=None,on_delete=models.SET_NULL)
	migrated = models.BooleanField(default=False)
	parent = TreeForeignKey('self',null=True,blank=True,related_name='children',on_delete=models.SET_NULL)
	verified = models.BooleanField(default=False)
	
	def __str__(self):
		return self.name + " (" + self.uuid + ")"
	def update_time(self):
		if self.created and not self.createtime:
			self.createtime = string2datetime(self.created)
			self.save()
	def update_lastchangeset(self):
		ws_history,created = Workspace.objects.get_or_create(name="git_history_%s" % self.component.name)
		if ws_history.ws_exist(stream=self.stream,component=self.component):
			ws_history.ws_delete(stream=self.stream,component=self.component)
		ws_history.uuid = ''
		ws_history.stream = None
		ws_history.snapshot = None
		ws_history.baseline = None
		ws_history.component = None
		ws_history.save()
		ws_history.ws_create()
		ws_history.ws_update()
		ws_history.ws_list()
		ws_history.baseline = self
		ws_history.component = self.component
		ws_history.save()
		ws_history.ws_add_component()
		ws_history.ws_list_changesets()
		ws_history.ws_delete(stream=self.stream,component=self.component)


class Snapshot(MPTTModel):
	uuid = models.CharField(max_length=64,unique=True)
	name = models.CharField(max_length=256,default='')
	comment = models.CharField(max_length=1024,default='')
	created = models.CharField(max_length=64,default='')
	createtime = models.DateTimeField(blank=True,null=True,default=None)
	baselines = models.ManyToManyField(Baseline)
	lastchangeset = TreeForeignKey(ChangeSet,null=True,on_delete=models.SET_NULL)
	changesets_listed = models.BooleanField(default=False)
	changesets_compared = models.BooleanField(default=False)
	migrated = models.BooleanField(default=False)
	parent = TreeForeignKey('self',null=True,blank=True,related_name='children',on_delete=models.SET_NULL)
	def __str__(self):
		return self.name + " (" + self.uuid + ") " + self.comment 
	def update_baselines(self):
		items = json.loads(shell.getoutput("%s list baselines -s %s -r rtc -m 10000 -j" % (scmcommand, self.uuid), clean=False))
		for item in items:
			if type(item) == type({}) and 'baselines' in item.keys():
				component,created = Component.objects.get_or_create(name=item['name'],uuid=item['uuid'])
				for sitem in item['baselines']:
					contributor,created = Contributor.objects.get_or_create(name=sitem['contributor'])
					baseline,created = Baseline.objects.get_or_create(uuid=sitem['uuid'],component=component)
					if created:
						shouter.shout("!!! found new created baseline for component %s, update component instead" % component.name)
						baseline.delete()
						component.update_baselines()
						baseline,created = Baseline.objects.get_or_create(uuid=sitem['uuid'],component=component)
					if baseline.name != sitem['name'] or baseline.comment != sitem['comment'] or baseline.bid != int(sitem['id']) or baseline.component != component:
						shouter.shout("!!! found strange baseline for snapshot")
						raise ValueError("Found Strange baseline, check please")
					self.baselines.add(baseline)
			else:
				shouter.shout("\t!!! problem update baselines for snapshot %s" % self.name)
	def update_time(self):
		if self.created and not self.createtime:
			self.createtime = string2datetime(self.created)
			self.save()

#class Stream(models.Model):
class Stream(MPTTModel):
	name = models.CharField(max_length=128)
	uuid = models.CharField(max_length=64,unique=True)
	category = models.ForeignKey(Category,default=3)
	parent = TreeForeignKey('self',null=True,blank=True,related_name='children',on_delete=models.SET_NULL)
	historys = models.ManyToManyField(ChangeSet,blank=True,related_name='instreams')
	component = models.ForeignKey(Component,related_name="forstreams",blank=True,null=True,default=None)
	components = models.ManyToManyField(Component,related_name="instreams",blank=True,default=None)
	snapshots = models.ManyToManyField(Snapshot)
	baselines = models.ManyToManyField(Baseline)
	project = models.ForeignKey(ProjectArea, blank=True, null=True, default=None)
	history_updated = models.BooleanField(default=False)
	historys_updated = models.ManyToManyField(Component,related_name="historyupdatedstreams",blank=True,default=None)
	history_partial = models.BooleanField(default=False)
	historys_partial = models.ManyToManyField(Component,related_name="historypartialstreams",blank=True,default=None)
	history_inconsistent = models.BooleanField(default=False)
	historys_inconsistent = models.ManyToManyField(Component,related_name="historyinconsistentstreams",blank=True,default=None)
	changesets_compared = models.BooleanField(default=False)
	lastchangeset = TreeForeignKey(ChangeSet,null=True,on_delete=models.SET_NULL,related_name="lastchangesets")
	firstchangeset = TreeForeignKey(ChangeSet,null=True,on_delete=models.SET_NULL,related_name="firstchangesets")
	migrated = models.BooleanField(default=False)
	verified = models.BooleanField(default=False)
	validated = models.BooleanField(default=False)

	def __str__(self):
		return self.uuid + " -> " + self.name

	def validate_branchingpoint(self):
		gitdir = os.path.join(migration_top,self.component.name,'gitdir')
		rtcdir = os.path.join(migration_top,self.component.name,'rtcdir',re.sub(r' ','',self.name))
		changesets = self.lastchangeset.get_ancestors(include_self=True).filter(migrated=False)
		workspace_stream = 'git_migrate_%s_%s' % (self.component.name, re.sub(r' ','', self.name))
		ws_migrate,created = Workspace.objects.get_or_create(name=workspace_stream)
		if ws_migrate.ws_exist(stream=self):
			shouter.shout("\t!!! Can not validate, workspace exists already, please inspect")
			return False
		ws_migrate.stream = None
		ws_migrate.component = None
		ws_migrate.baseline = None
		ws_migrate.save()
		ws_migrate.ws_create()
		### set .stream and .component property
		ws_migrate.stream = self
		ws_migrate.component = self.component
		ws_migrate.save()
		ws_migrate.ws_update()
		ws_migrate.ws_list()
		ws_migrate.ws_prepare_initial()
		rtc_initialize(rtcdir, gitdir=gitdir, workspace=ws_migrate, load=True, component=self.component)
		if git_got_changes(gitdir=rtcdir):
			return False
		else:
			self.validated = True
			self.save()
			return True

	def git_sync_children_streams(self,rtcdir='.'):
		if not self.firstchangeset or not self.lastchangeset or not self.migrated:
			shouter.shout("\t... nothing to update, not migrated or no firstchangeset or no lastchangeset")
			sys.exit(0)
		for changeset in list(self.lastchangeset.get_ancestors().filter(level__gt=self.firstchangeset.level)) + [self.lastchangeset]:
			if changeset.firstchangesets.all():
				for s in changeset.firstchangesets.all():
					print(subprocess.check_output("git -C %s checkout -b %s %s" % (rtcdir, re.sub(r' ','',s.name), changeset.commit.commitid),shell=True).decode())
					shell.execute("git -C %s checkout %s" % (rtcdir,re.sub(r' ','',self.name)))
					print(subprocess.check_output("git -C %s push origin :refs/heads/%s; echo test only ;git -C %s push origin %s:refs/heads/%s" % (rtcdir, re.sub(r' ','',s.name), rtcdir, re.sub(r' ','',s.name), re.sub(r' ','',s.name)), shell=True).decode())

	def determine_branching(self,stream0=None):
		if stream0:
			c0 = None
			cl0 = list(stream0.lastchangeset.get_ancestors()) + [stream0.lastchangeset]
			cl = list(self.lastchangeset.get_ancestors()) + [self.lastchangeset]
			min_length = min(len(cl0),len(cl))
			cl = cl[:min_length]
			cl0 = cl0[:min_length]
			times_tried = 0
			while len(cl) > 100:
				times_tried += 1
				shouter.shout("\t ... try time %g to determine branching point, %g changesets left" % (times_tried, len(cl)))
				index = int(len(cl) / 2)
				if cl[index] != cl0[index]:
					cl = cl[:index]
					cl0 = cl0[:index]
				else:
					cl = cl[index:]
					cl0 = cl0[index:]
			cl.reverse()
			cl0.reverse()
			for i in range(len(cl)):
				if cl[i] == cl0[i]:
					c0 = cl[i]
					break
		#	cl.reverse()
		#	for c in cl:
		#		if c in cl0:
		#			c0 = c
		#			break
			if c0:
				self.firstchangeset = c0
			self.parent = stream0
			self.save()
		else:
			if not self.firstchangeset:
				self.firstchangeset = self.lastchangeset.get_ancestors().first()
				self.save()

	def update_baselines_changesets(self,post_incremental=False):
		history_dir = os.path.join(settings.BASE_DIR,'tmp',self.component.name)
		compare_file = os.path.join(history_dir, "compare_%s" % re.sub(r' ','',self.name))
		print("\t... update baselines and their changesets for stream %s" % self.name)
		shouter.shout("\t ...check history_updated and history_partial property to determine if we do it now or later")
		if not self.history_updated:
			shouter.shout("\t !!! you need first handle the changeset history, with parameter --infoupdate")
			sys.exit(9)
		elif self.history_partial or self.history_inconsistent:
			shouter.shout("\t .!. handle compare later, since history_partial or history_inconsistent is true. You may need manually copy the history and put it the proper location with proper file name")
			self.history_updated = False
			self.history_partial = False
			self.save()
			sys.exit(9)
		else:
			ws_history,created = Workspace.objects.get_or_create(name="git_history_%s" % self.component.name)
			if ws_history.ws_exist(stream=self):
				ws_history.ws_delete(stream=self)
			ws_history.uuid = ''
			ws_history.stream = None
			ws_history.snapshot = None
			ws_history.baseline = None
			ws_history.component = None
			ws_history.save()
			ws_history.ws_create()
			ws_history.ws_update()
			ws_history.ws_list()
			ws_history.component = self.component
			if post_incremental:
				last_processed_baseline = None
				if not self.changesets_compared:
					shouter.shout("\t...You can now run --infoupdate --streams [%g]" % self.id)
					return ""
				for bis in self.baselineinstream_set.order_by('baseline__level'):
					if bis.historys_processed:
						last_processed_baseline = bis.baseline
				if last_processed_baseline:
					shouter.shout("\t... updating changesets from last processed baseline %s on stream %s" % (last_processed_baseline.uuid, self.name))
					ws_history.baseline = last_processed_baseline
			ws_history.save()
			ws_history.ws_add_component()
			#ws_history.ws_unset_flowtarget()
			ws_history.ws_set_flowtarget(target=self)
			if not post_incremental and os.path.exists(compare_file):
				shouter.shout("\t.!.compare had been completed before, take it here to save time")
				with open(compare_file,'r') as f:
					items = json.load(f)
			else:
				items = json.loads(shell.getoutput("%s compare -f i -I cbsw -D 'yyyy-MM-dd HH:mm:ss' -r rtc -c %s workspace %s stream %s -j" % (scmcommand, self.component.uuid, ws_history.uuid, self.uuid), clean=False))
				if not post_incremental:
					with open(compare_file,'w') as f:
						json.dump(items,f)
			output = []
			output_changesets = []
			for i in range(len(items['direction'][0]['components'])):
				if items['direction'][0]['components'][i]['name'] == self.component.name:
					if 'baselines' in items['direction'][0]['components'][i].keys():
						output = items['direction'][0]['components'][i]['baselines']
					if 'changesets' in items['direction'][0]['components'][i].keys():
						output_changesets = items['direction'][0]['components'][i]['changesets']
				else:
					shouter.shout("\t.!. bypassing component %s" % items['direction'][0]['components'][i]['name'])
			for item in output_changesets:
				if 'uuid' in item.keys() and item['uuid']:
					changeset = None
					created = None
					try:
						changeset,created = ChangeSet.objects.get_or_create(uuid=item['uuid'])
					except ChangeSet.MultipleObjectsReturned:
						for changesett in ChangeSet.objects.filter(uuid=item['uuid']).order_by('sequence'):
							if changesett == self.lastchangeset or changesett in self.lastchangeset.get_ancestors().all():
								changeset = changesett
						if not changeset:
							changeset,created = ChangeSet.objects.get_or_create(uuid=item['uuid'], sequence=changesett.sequence + 1)
					if created:
						changeset.delete()
						shouter.shout("\t!!! you need update your stream history first with --infoupdate --incremetal --streams [%g]" % self.id)
						raise ValueError("!!! got new changeset in compare, should've been created earlier, are you refresh the new changes? %s" % item['uuid'])
					shouter.shout("\t...post baseline changeset %s" % (changeset))
					if not changeset.compared:
						if post_incremental:
							shouter.shout("\t\t... updating uncompared changeset %s" % changeset.uuid)
						changeset.comment = item.get('comment','NOCOMMENT')
						author,created = Author.objects.get_or_create(uuid=item['author']['uuid'])
						if created:
							author.name = item['author']['userName']
							author.mail = item['author']['mail']
							author.userid = item['author']['userId']
							author.save()
						changeset.author = author
						if 'workitems' in item.keys():
							for subitem in item['workitems']:
								workitem,created = Workitem.objects.get_or_create(uuid=subitem['uuid'],number=subitem['workitem-number'])
								if created:
									workitem.label = subitem['workitem-label']
									workitem.save()
								changeset.workitems.add(workitem)
						changeset.created = item['creationDate']
						changeset.createtime = string2datetime(changeset.created)
						changeset.compared = True
						changeset.save()
				else:
					raise ValueError("!!! can not find uuid info in the changeset in compare result")
			for i in range(len(output)):
				print("%s\t%s\t%s" % (output[i]['name'],output[i]['uuid'], output[i]['item-type']))
				baseline, created = Baseline.objects.get_or_create(uuid=output[i]['uuid'])
				if created:
					raise ValueError("!!! created a new baseline %s for stream %s, however, it should have been created before this" % (output[i]['name'],self.name))
				baselineinstream, created = BaselineInStream.objects.get_or_create(baseline=baseline,stream=self)
				if not created:
					shouter.shout("\t .!. got an existing baselineinstream which indicates that it probably has been processed")
					if baselineinstream.historys_processed:
						shouter.shout("\t .!. this baseline in stream %s has been processed" % baseline.uuid)
						continue
				changesets = output[i].get('changesets',[])
				baselineinstream.update(changesets=changesets)
		self.changesets_compared = True
		self.save()
		shouter.shout("... finished for stream %s" % self.name)

	def update_baselines(self,post_incremental=False):
		print("\t... update baselines for stream %s" % self.name)
		items = json.loads(shell.getoutput("%s list baselines -r rtc -w %s -C %s -j -m 10000" % (scmcommand, self.uuid, self.component.uuid), clean=False))
		for item in items:
			baselinep = None
			baselines = []
			if type(item) == type({}) and 'baselines' in item.keys():
				for sitem in item['baselines']:
					if 'uuid' in sitem.keys() and 'id' in sitem.keys() and 'creationDate' in sitem.keys():
						if not post_incremental:
							shouter.shout("%s\t%s\t%s" % (sitem['uuid'], sitem.get('name',"NONAME"), sitem['creationDate']))
						contributor,created = Contributor.objects.get_or_create(name=sitem.get('contributor','NOCONTRIBUTOR'))
						baseline,created = Baseline.objects.get_or_create(uuid=sitem['uuid'],component=self.component)
						if created:
							shouter.shout("!!! baseline should have been created by component level baseline update, perhaps this is a new one: %s" % sitem['creationDate'])
							input("press anykey to continue or break to inspect")
							baseline.name = sitem.get('name','NONAME')
							baseline.bid = int(sitem['id'])
							baseline.comment = sitem.get('comment','NOCOMMENT')
							baseline.contributor = contributor
							baseline.created = sitem['creationDate']
							baseline.createtime = string2datetime(sitem['creationDate'])
							baseline.save()
						else:
							if  baseline.name != sitem.get('name','NONAME') or baseline.comment != sitem.get('comment','NOCOMMENT') or baseline.bid != int(sitem['id']) or baseline.component != self.component:
								shouter.shout("!!! found suspect/strange baseline for snapshot")
								raise ValueError("Found Suspect/Strange baseline, check please")
						baselines.append(baseline)
						self.baselines.add(baseline)
					else:
						shouter.shout(".!. met incomplete | repeated baseline for component %s" % self.name)
						#input("...... any key to continue or break")
				def baseline_createtime(baseline):
					return baseline.createtime
				baselines = sorted(list(set(baselines)), key=baseline_createtime, reverse=True)
				for baseline in baselines:
					if not post_incremental:
						shouter.shout("%s\t%s" % (baseline.uuid, baseline.createtime))
					if baselinep:
						if not baselinep.parent:
							baselinep.parent = baseline
							baselinep.save()
						elif not post_incremental and baselinep.parent != baseline:
							shouter.shout("!!! found strange baseline for snapshot %s: parent %s, should it be %s?" % (baselinep.uuid, baselinep.parent.uuid,baseline.uuid))
							shouter.shout("\t !!! should we continue or break? input y to continue or else to break")
							answer = input("\tyes or no? y/n  ")
							if answer.strip() != 'y' and answer.strip() != 'Y':
								raise ValueError("Found Strange baseline, check please")
							with open(os.path.join(settings.BASE_DIR,'tmp','.issues'),'w') as f:
								f.write("Issue for baseline %s of stream %s %s, manual confirm needed!\n" % (baseline.uuid, baselinep.uuid, self.name))
						else:
							if not post_incremental:
								shouter.shout("... found parent baseline %s" % baseline.uuid)
					baselinep = baseline

	def update_snapshots(self):
		items = json.loads(shell.getoutput("%s list snapshots -r rtc -j -v -m 2000 %s" % (scmcommand, self.uuid), clean=False))
		if type(items) == type({}) and 'snapshots' in items.keys():
			snapshotp = None
			for item in items['snapshots']:
				uuid = item['uuid']
				time = item['creationDate']
				snapshot,created = Snapshot.objects.get_or_create(uuid=uuid)
				if snapshotp:
					if not snapshotp.parent:
						snapshotp.parent = snapshot
						snapshotp.save()
					elif snapshotp.parent != snapshot:
						shouter.shout("found strange snapshot for stream %s" % self.name)
						raise ValueError("Found strange snapshot, investigate please")
					else:
						pass
				if created:
					snapshot.name = item['name']
					snapshot.comment = item['comment']
					snapshot.created = item['creationDate']
					snapshot.createtime = string2datetime(item['creationDate'])
					snapshot.save()
				else:
					if snapshot.name != item['name'] or snapshot.comment != item['comment'] or snapshot.created != item['creationDate']:
						shouter.shout("found strange snapshot for stream %s" % self.name)
						raise ValueError("Found strange snapshot, investigate please")
				snapshotp = snapshot
				self.snapshots.add(snapshot)
	def update_history(self,initial=False,post_incremental=False):
		history_dirbase = os.path.join(settings.BASE_DIR,'History')
		history_dir = os.path.join(settings.BASE_DIR,'tmp',self.component.name)
		subprocess.check_output("mkdir -p %s ; exit 0" % history_dir,shell=True)
		history_filename = os.path.join(history_dirbase,'history_%s_%s' % (self.component.name, self.name))
		uuid_file = os.path.join(history_dir, "uuid_%s" % re.sub(r' ','',self.name))
		changesetp = None
		updated = True
		history_updated = False
		history_inconsistent = False
		history_partial = True
		bypass_number = 300
		founded_number = 0
		TREE_SEG_LIMIT = 2000 
		new_changesets = []
		if post_incremental:
			if not self.history_updated:
				shouter.shout("\t!!! stream history not updated yet, can not do incremental")
				input("ctrl + C to break")
			elif self.history_partial or self.history_inconsistent:
				shouter.shout("\t!!! stream history partial or inconsistent, can not do incremental")
				input("ctrl + C to break")
			else:
				shouter.shout("\t... stream history updated and consistent, incremental to refresh new changesets")
				command = "%s show history -r rtc -w %s -m 200 -j -C %s" % (scmcommand, self.uuid, self.component.uuid)
				historys = json.loads(shell.getoutput(command,clean=False))
				uuids = list(map(lambda x: x['uuid'],  historys['changes']))
				for i in range(len(uuids)):
					uuid = uuids[i]
					if uuid:
						# try from sequence 1
						created = False
						changeset = None
						sequence = 0
						short_break = False
						path_found = True
						while not changeset:
							sequence += 1
							if sequence > 1:
								shouter.shout("\t .!. trying sequence %g" % sequence)
							try:
								## changeset exists, see if we can verify to some extent, especially if there is multiple already
								changeset = ChangeSet.objects.get(uuid=uuid,sequence=sequence)
								founded_number += 1
								shouter.shout("\t\t... got %g changesets so far, verify if we found the path already" % i)
								j = i
								changesett = changeset
								while j < min(500, len(uuids) - 1):
									j += 1
									if changesett.parent:
										changesett = changesett.parent
										if changesett.uuid != uuids[j]:
											shouter.shout("\t\t.!. sequence %g is not the proper changeset, try next" % sequence)
											path_found = False
											changeset = None
											break
									else:
										shouter.shout("\t.!. found orphen changeset, manually verify if it is good or not")
										input("any key to continue or break")
								if changeset and changesetp:
									if not changesetp.parent:
										shouter.shout("\t...set parent")
										changesetp.parent = changeset
										changesetp.save()
									elif changesetp.parent == changeset:
										shouter.shout("\t...found parent at level %g" % changeset.level)
									else:
										history_inconsistent = True
										self.history_inconsistent = history_inconsistent
										self.save()
										raise ValueError("\tfound problem for update_history(), manully check please")
								else:
									pass
								if path_found:
									history_partial = False
									shouter.shout("\t.!. bypassing the display of rest changesets since we found the path already")
									shouter.shout("\t\t... adding them into history, it may cost long time")
									self.history_partial = history_partial
									self.save()
									short_break = True
								else:
									shouter.shout("\t... found existing changeset %s" % uuid)
							except ChangeSet.DoesNotExist:
								## create new changeset
								changeset, created = ChangeSet.objects.get_or_create(uuid=uuid,sequence=sequence)
								shouter.shout("\t... picked up new changeset %s" % uuid)
								founded_number = 0
								if not new_changesets:
									shouter.shout("\t... picked up the first new changeset %s, set new lastchangeset now" % uuid)
									self.lastchangeset = changeset
									self.save()
								new_changesets.append(changeset)
								if changesetp:
									if not changesetp.parent:
										shouter.shout("\t...set parent")
										changesetp.parent = changeset
										changesetp.save()
									elif changesetp.parent == changeset:
										shouter.shout("\t...found parent at level %g" % changeset.level)
									else:
										history_inconsistent = True
										self.history_inconsistent = history_inconsistent
										self.save()
										raise ValueError("\tfound problem for update_history(), manually verify please")
								else:
									pass
						if short_break:
							break
						changesetp = changeset
					else:
						shouter.shout("\t.!. found non uuid changes, verify please")
						history_inconsistent = True
						self.history_inconsistent = history_inconsistent
						self.save()
						input("press any key to continue otherwise break")
				if new_changesets:
					shouter.shout("\t... adding %g new picked up changesets into history" % len(new_changesets))
					for new_changeset in new_changesets:
						pass
				
		else:
			if os.path.exists(history_filename):
				subprocess.check_output("mkdir -p %s; exit 0" % history_dir,shell=True)
				with open(history_filename,'r') as f:
					lines = f.read().strip().split('\n')
				uuids = list(map(lambda x: re.sub(r'.*com.ibm.team.scm.ChangeSet/|.Workspace=.*','',x.strip()), lines))
				with open(uuid_file,'w') as f:
					json.dump(uuids,f)
				if initial:
					uuids.reverse()
					changesets = []
					if ChangeSet.objects.all():
						shouter.shout("\t!!! you have existing changesets already, can not perform intial history update")
						sys.exit(9)
					for i in range(len(uuids)):
						uuid = uuids[i]
						if changesetp:
							changeset = ChangeSet(id=i+1, uuid=uuid,lft=i+1,rght=2 * len(uuids) - i,level=i,tree_id=1, parent_id=changesetp.id)
						else:
							changeset = ChangeSet(id=i+1, uuid=uuid,lft=i+1,rght=2 * len(uuids) - i,level=i,tree_id=1)
						changesets.append(changeset)
						changesetp = changeset
					if len(changesets) <= TREE_SEG_LIMIT:
						ChangeSet.objects.bulk_create(changesets)
						time.sleep(5)
					else:
						for i in range(int(len(changesets) / TREE_SEG_LIMIT)):
							changesets_slice = changesets[i * TREE_SEG_LIMIT: ( i + 1 ) * TREE_SEG_LIMIT]
							shouter.shout("\t ... adding slice %g" % i)
							ChangeSet.objects.bulk_create(changesets_slice)
							time.sleep(5)
						shouter.shout("\t ... adding slice leftover")
						changesets_slice = changesets[( i + 1 ) * TREE_SEG_LIMIT:]
						ChangeSet.objects.bulk_create(changesets_slice)
						time.sleep(5)
					shouter.shout("\t.!. add all changesets to history, this is only valid for trunk, the first stream to handle")
					for c in ChangeSet.objects.all():
						##!! this is only valid for trunk, the first stream to handle
						pass
					if not self.lastchangeset:
						self.lastchangeset = ChangeSet.objects.get(id=changeset.id)
						self.firstchangeset = ChangeSet.objects.get(id=changesets[0].id)
						self.save()
					history_updated = True
					history_partial = False
				else:
					## partial history for long streams
					for i in range(len(uuids)):
						uuid = uuids[i]
						if uuid:
							# try from sequence 1
							created = False
							changeset = None
							sequence = 0
							short_break = False
							path_found = True
							while not changeset:
								sequence += 1
								if sequence > 1:
									shouter.shout("\t .!. trying sequence %g" % sequence)
								try:
									## changeset exists, see if we can verify to some extent, especially if there is multiple already
									changeset = ChangeSet.objects.get(uuid=uuid,sequence=sequence)
									founded_number += 1
									shouter.shout("\t\t... got %g changesets so far, verify if we found the path already" % i)
									j = i
									changesett = changeset
									while j < min(500, len(uuids) - 1):
										j += 1
										if changesett.parent:
											changesett = changesett.parent
											if changesett.uuid != uuids[j]:
												shouter.shout("\t\t.!. sequence %g is not the proper changeset, try next" % sequence)
												path_found = False
												changeset = None
												break
										else:
											shouter.shout("\t.!. found orphen changeset, manually verify if it is good or not")
											input("any key to continue or break")
									if changeset and changesetp:
										if not changesetp.parent:
											shouter.shout("\t...set parent")
											changesetp.parent = changeset
											changesetp.save()
										elif changesetp.parent == changeset:
											shouter.shout("\t...found parent at level %g" % changeset.level)
										else:
											history_inconsistent = True
											self.history_inconsistent = history_inconsistent
											self.save()
											raise ValueError("\tfound problem for update_history(), manully check please")
									elif changeset and not self.lastchangeset:
										self.lastchangeset = changeset
										self.save()
									else:
										pass
									if path_found:
										shouter.shout("\t... found existing changeset %s" % uuid)
										history_partial = False
										shouter.shout("\t.!. bypassing the display of rest changesets since we found the path already")
										shouter.shout("\t\t... adding them into history, it may cost long time")
										while changeset.parent:
											changeset = changeset.parent
										self.history_partial = history_partial
										self.save()
										short_break = True
								except ChangeSet.DoesNotExist:
									## create new changeset
									changeset, created = ChangeSet.objects.get_or_create(uuid=uuid,sequence=sequence)
									shouter.shout("\t... picked up new changeset %s" % uuid)
									founded_number = 0
									if changesetp:
										if not changesetp.parent:
											shouter.shout("\t...set parent")
											changesetp.parent = changeset
											changesetp.save()
										elif changesetp.parent == changeset:
											shouter.shout("\t...found parent at level %g" % changeset.level)
										else:
											history_inconsistent = True
											self.history_inconsistent = history_inconsistent
											self.save()
											raise ValueError("\tfound problem for update_history(), manually verify please")
									elif not self.lastchangeset:
										self.lastchangeset = changeset
										self.save()
									else:
										pass
							if short_break:
								break
							changesetp = changeset
						else:
							shouter.shout("\t.!. found non uuid changes, verify please")
							history_inconsistent = True
							self.history_inconsistent = history_inconsistent
							self.save()
							input("press any key to continue otherwise break")
					history_updated = True
				## update with show history to pick up new changesets that happen after the history files with a smaller number of maximum
				shouter.shout("\t... trying to pick up new changesets after the history file is produced")
				command = "%s show history -r rtc -w %s -m 1000 -j -C %s" % (scmcommand, self.uuid, self.component.uuid)
				historys = json.loads(shell.getoutput(command,clean=False))
				uuids = list(map(lambda x: x['uuid'],  historys['changes']))
				changesetp = None
				for i in range(0,len(uuids)):
					uuid = uuids[i]
					if uuid:
						# try from sequence 1
						created = False
						changeset = None
						sequence = 0
						short_break = False
						path_found = True
						while not changeset:
							sequence += 1
							if sequence > 1:
								shouter.shout("\t .!. trying sequence %g" % sequence)
							try:
								## changeset exists, see if we can verify to some extent, especially if there is multiple already
								changeset = ChangeSet.objects.get(uuid=uuid,sequence=sequence)
								founded_number += 1
								shouter.shout("\t\t... got %g changesets so far, verify if we found the path already" % i)
								j = i
								changesett = changeset
								while j < min(500, len(uuids) - 1):
									j += 1
									if changesett.parent:
										changesett = changesett.parent
										if changesett.uuid != uuids[j]:
											shouter.shout("\t\t.!. sequence %g is not the proper changeset, try next" % sequence)
											path_found = False
											changeset = None
											break
									else:
										shouter.shout("\t.!. found orphen changeset, manually verify if it is good or not")
										input("any key to continue or break")
								if changeset and changesetp:
									if not changesetp.parent:
										shouter.shout("\t...set parent")
										changesetp.parent = changeset
										changesetp.save()
									elif changesetp.parent == changeset:
										shouter.shout("\t...found parent at level %g" % changeset.level)
									else:
										history_inconsistent = True
										self.history_inconsistent = history_inconsistent
										self.save()
										raise ValueError("\tfound problem for update_history(), manully check please")
								else:
									pass
								if path_found:
									history_partial = False
									shouter.shout("\t.!. bypassing the display of rest changesets since we found the path already")
									shouter.shout("\t\t... adding them into history, it may cost long time")
									self.history_partial = history_partial
									self.save()
									short_break = True
								else:
									shouter.shout("\t... found existing changeset %s" % uuid)
							except ChangeSet.DoesNotExist:
								## create new changeset
								changeset, created = ChangeSet.objects.get_or_create(uuid=uuid,sequence=sequence)
								shouter.shout("\t... picked up new changeset %s" % uuid)
								founded_number = 0
								if not new_changesets:
									shouter.shout("\t... picked up the first new changeset %s, set new lastchangeset now" % uuid)
									self.lastchangeset = changeset
									self.save()
								new_changesets.append(changeset)
								if changesetp:
									if not changesetp.parent:
										shouter.shout("\t...set parent")
										changesetp.parent = changeset
										changesetp.save()
									elif changesetp.parent == changeset:
										shouter.shout("\t...found parent at level %g" % changeset.level)
									else:
										history_inconsistent = True
										self.history_inconsistent = history_inconsistent
										self.save()
										raise ValueError("\tfound problem for update_history(), manually verify please")
								else:
									pass
						if short_break:
							break
						changesetp = changeset
					else:
						shouter.shout("\t.!. found non uuid changes, verify please")
						history_inconsistent = True
						self.history_inconsistent = history_inconsistent
						self.save()
						input("press any key to continue otherwise break")
				if new_changesets:
					shouter.shout("\t... adding %g new picked up changesets into history" % len(new_changesets))
					for new_changeset in new_changesets:
						pass
			else:
				shouter.shout(".!.updating the history changeset for stream: %s, note that the cmd show history is limited, you need to prepare the history file if the limit 1000 changsets are not sufficient" % self.name)
				ws_history,created = Workspace.objects.get_or_create(name="git_history_%s" % self.component.name)
				ws_history.stream = self
				ws_history.save()
				if ws_history.ws_exist():
					ws_history.ws_delete()
				ws_history.ws_create()
				ws_history.ws_update()
				ws_history.ws_list()
				command = "lscm show history -r rtc -w %s -m 1000 -j -C %s" % (ws_history.uuid, self.component.uuid)
				historys = json.loads(shell.getoutput(command,clean=False))
				uuids = list(map(lambda x: x['uuid'],  historys['changes']))
				with open(uuid_file,'w') as f:
					json.dump(uuids,f)
				if initial:
					if ChangeSet.objects.all():
						shouter.shout("\t!!! you have existing changesets already, can not perform intial history update")
						sys.exit(9)
					if len(uuids) == 1000:
						if USE_HISTORY_FILE:
							shouter.shout("\t!!! show history for your streambase return more than 1000 changesets, you need provide the history file for this")
							sys.exit(9)
						else:
							shouter.shout("\t.!. trying to use lscm compare command to get the full list for you")
							shouter.shout("\t!!! it turns out that 'show history' and 'compare' return changesets in different sequences")
							shouter.shout("\t!!! set your settings USE_HISTORY_FILE to True, get the history file from eclipse GUI and rerun the program")
							sys.exit(9)
							if os.path.exists(uuid_file + "-compare"):
								shouter.shout("\t\t... found existing compare result, using it instead to save time")
								with open(uuid_file + "-compare",'r') as f:
									uuids = json.load(f)
									uuids.reverse()
							else:
								ws_history,created = Workspace.objects.get_or_create(name="git_history_%s" % self.component.name)
								if ws_history.ws_exist(stream=self):
									ws_history.ws_delete(stream=self)
								ws_history.uuid = ''
								ws_history.stream = None
								ws_history.snapshot = None
								ws_history.baseline = None
								ws_history.component = None
								ws_history.save()
								ws_history.ws_create()
								ws_history.ws_update()
								ws_history.ws_list()
								ws_history.component = self.component
								ws_history.save()
								ws_history.ws_add_component()
								#ws_history.ws_unset_flowtarget()
								ws_history.ws_set_flowtarget(target=self)
								items = json.loads(shell.getoutput("%s show history -r rtc -w %s -j -C %s" % (scmcommand, ws_history.uuid, self.component.uuid), clean=False))
								uuids = list(map(lambda x: x['uuid'],  items['changes']))
								items = json.loads(shell.getoutput("%s compare -f i -I cbsw -D 'yyyy-MM-dd HH:mm:ss' -r rtc -c %s workspace %s stream %s -j" % (scmcommand, self.component.uuid, ws_history.uuid, self.uuid), clean=False))
								for comp in items['direction'][0]['components']:
									if comp == self.component.name:
										if 'baselines' in comp.keys():
											for bl in comp['baselines']:
												if 'changesets' in bl.keys():
													for cs in bl['changesets']:
														if 'uuid' in cs.keys():
															uuids.append(cs['uuid'])
							changesets = []
							for i in range(0,len(uuids)):
								uuid = uuids[i]
								if changesetp:
									changeset = ChangeSet(id=i+1, uuid=uuid,lft=i+1,rght=2 * len(uuids) - i,level=i,tree_id=1, parent_id=changesetp.id)
								else:
									changeset = ChangeSet(id=i+1, uuid=uuid,lft=i+1,rght=2 * len(uuids) - i,level=i,tree_id=1)
								changesets.append(changeset)
								changesetp = changeset
							if len(changesets) <= TREE_SEG_LIMIT:
								ChangeSet.objects.bulk_create(changesets)
								time.sleep(5)
							else:
								for i in range(0,int(len(changesets) / TREE_SEG_LIMIT)):
									changesets_slice = changesets[i * TREE_SEG_LIMIT: ( i + 1 ) * TREE_SEG_LIMIT]
									shouter.shout("\t ... adding slice %g" % i)
									ChangeSet.objects.bulk_create(changesets_slice)
									time.sleep(5)
								shouter.shout("\t ... adding slice leftover")
								changesets_slice = changesets[( i + 1 ) * TREE_SEG_LIMIT:]
								ChangeSet.objects.bulk_create(changesets_slice)
								time.sleep(5)
							for c in ChangeSet.objects.all():
								##!! this is only valid for trunk, the first stream to handle
								pass
							if not self.lastchangeset:
								self.lastchangeset = ChangeSet.objects.get(id=changeset.id)
								self.save()
							history_updated = True
							history_partial = False
							uuids.reverse()
							with open(uuid_file + "-compare",'w') as f:
								json.dump(uuids,f)
				if not history_updated:
					for i in range(0,len(uuids)):
						uuid = uuids[i]
						if uuid:
							# try from sequence 1
							created = False
							changeset = None
							sequence = 0
							short_break = False
							path_found = True
							while not changeset:
								sequence += 1
								if sequence > 1:
									shouter.shout("\t .!. trying sequence %g" % sequence)
								try:
									## changeset exists, see if we can verify to some extent, especially if there is multiple already
									changeset = ChangeSet.objects.get(uuid=uuid,sequence=sequence)
									founded_number += 1
									shouter.shout("\t\t... got %g changesets so far, verify if we found the path already" % i)
									j = i
									changesett = changeset
									while j < min(500, len(uuids) - 1):
										j += 1
										if changesett.parent:
											changesett = changesett.parent
											if changesett.uuid != uuids[j]:
												shouter.shout("\t\t.!. sequence %g is not the proper changeset, try next" % sequence)
												path_found = False
												changeset = None
												break
										else:
											shouter.shout("\t.!. found orphen changeset, manually verify if it is good or not")
											input("any key to continue or break")
									if changeset and changesetp:
										if not changesetp.parent:
											shouter.shout("\t...set parent")
											changesetp.parent = changeset
											changesetp.save()
										elif changesetp.parent == changeset:
											shouter.shout("\t...found parent at level %g" % changeset.level)
										else:
											history_inconsistent = True
											self.history_inconsistent = history_inconsistent
											self.save()
											raise ValueError("\tfound problem for update_history(), manully check please")
									elif changeset and not self.lastchangeset:
										self.lastchangeset = changeset
										self.save()
									else:
										pass
									if path_found:
										shouter.shout("\t... found existing changeset %s" % uuid)
										history_partial = False
										shouter.shout("\t.!. bypassing the display of rest changesets since we found the path already")
										shouter.shout("\t\t... adding them into history, it may cost long time")
										while changeset.parent:
											changeset = changeset.parent
										self.firstchangeset = changeset
										self.history_partial = history_partial
										self.save()
										short_break = True
								except ChangeSet.DoesNotExist:
									## create new changeset
									changeset, created = ChangeSet.objects.get_or_create(uuid=uuid,sequence=sequence)
									shouter.shout("\t... picked up new changeset %s" % uuid)
									founded_number = 0
									if changesetp:
										if not changesetp.parent:
											shouter.shout("\t...set parent")
											changesetp.parent = changeset
											changesetp.save()
										elif changesetp.parent == changeset:
											shouter.shout("\t...found parent at level %g" % changeset.level)
										else:
											history_inconsistent = True
											self.history_inconsistent = history_inconsistent
											self.save()
											raise ValueError("\tfound problem for update_history(), manually verify please")
									elif not self.lastchangeset:
										self.lastchangeset = changeset
										self.save()
									else:
										pass
							if short_break:
								break
							changesetp = changeset
						else:
							shouter.shout("\t.!. found non uuid changes, verify please")
							history_inconsistent = True
							self.history_inconsistent = history_inconsistent
							self.save()
							input("press any key to continue otherwise break")
					if not self.firstchangeset:
						self.firstchangeset = changeset
						self.save()
					history_updated = True
					#if len(uuids) < 1000:
					if short_break:
						history_partial = False
					elif len(uuids) < 1000:
						history_partial = False
					else:
						input("\t !!!did not find hook with other streams, terminate here")
						
			self.history_updated = history_updated
			self.history_partial = history_partial
			self.history_inconsistent = history_inconsistent
		self.save()

class BaselineInStream(models.Model):
	baseline = models.ForeignKey(Baseline)
	stream = models.ForeignKey(Stream)
	historys = models.ManyToManyField(ChangeSet,related_name="changesethistory",blank=True)
	historys_processed = models.BooleanField(default=False)
	lastchangeset = TreeForeignKey(ChangeSet,related_name='lastchangeset',null=True,on_delete=models.SET_NULL)
	firstchangeset = TreeForeignKey(ChangeSet,related_name='firstchangeset',null=True,on_delete=models.SET_NULL)
	migrated = models.BooleanField(default=False)
	out_verify = models.TextField(default='')
	verified = models.BooleanField(default=False)
	
	class Meta:
		unique_together = ('baseline','stream')
		ordering = ('stream','-baseline')

	def __str__(self):
		return "stream %s -> baseline %s" % (self.stream.uuid, self.baseline.uuid)

	def validate_baseline(self):
		gitdir = os.path.join(migration_top,self.stream.component.name,'gitdir')
		rtcdir = os.path.join(migration_top,self.stream.component.name,'rtcdir',re.sub(r' ','',self.stream.name) + '_verify')
		if not os.path.exists(rtcdir):
			ws_verify,created = Workspace.objects.get_or_create(name='git_verify_%s_%s' % (self.stream.component.name, re.sub(r' ','',self.stream.name)))
			ws_verify.component = self.stream.component
			ws_verify.stream = self.stream
			ws_verify.save()
			rtc_initialize(rtcdir,gitdir=gitdir,workspace=ws_verify,component=self.stream.component,verifying=True)
		if self.historys.all():
			shouter.shout("\t... verifying baseline in stream %s" % self.baseline.name)
			print("%-4g%-4g %-5g %s %s" % (self.baseline.level, self.baseline.bid, self.lastchangeset.level, self.lastchangeset.uuid, self.baseline.uuid))
			ws_verify,created = Workspace.objects.get_or_create(name='git_verify_%s_%s' % (self.stream.component.name, re.sub(r' ','',self.stream.name)))
			if not created:
				ws_verify.delete()
			ws_verify,created = Workspace.objects.get_or_create(name='git_verify_%s_%s' % (self.stream.component.name, re.sub(r' ','',self.stream.name)))
			if ws_verify.ws_exist(stream=self.stream):
				ws_verify.ws_delete(stream=self)
			ws_verify.ws_create()
			ws_verify.component = self.stream.component
			ws_verify.baseline = self.baseline
			ws_verify.stream = self.stream
			ws_verify.save()
			ws_verify.ws_add_component()
			ws_verify.ws_list_component()
			ws_verify.ws_set_flowtarget()
			ws_verify.ws_list_flowtarget()
			#ws_verify.ws_set_component()
			lastchangeset = self.lastchangeset
			if lastchangeset:
				lastchangeset.refresh_from_db()
			if lastchangeset and lastchangeset.commit:
				shell.getoutput("git -C %s add -A; exit 0" % rtcdir, clean=False)
				if git_got_changes(gitdir=rtcdir):
					shell.getoutput("git -C %s commit -m test; exit 0" % rtcdir, clean=False)
				shell.getoutput("git -C %s checkout %s" % ( rtcdir, re.sub(r' ','',self.stream.name)))
				shell.getoutput("git -C %s pull" % ( rtcdir))
				output = shell.getoutput("git -C %s branch" % rtcdir, clean=False)
				if re.match(".*%s" % self.baseline.uuid, output):
					shell.getoutput("git -C %s branch -D %s" % ( rtcdir, self.baseline.uuid))
				shell.getoutput("git -C %s checkout -b %s %s" % (rtcdir, self.baseline.uuid, lastchangeset.commit.commitid))
				try:
					ws_verify.ws_load(load_dir=rtcdir)
					shell.getoutput("git -C %s add -A" % rtcdir)
					if git_got_changes(gitdir=rtcdir):
						shouter.shout("\t!!! verification for baseline in stream %s failed" % self.baseline.name)
						ws_verify.ws_unload(load_dir=rtcdir)
						shell.getoutput("git -C %s add -A; exit 0" % rtcdir, clean=False)
						if git_got_changes(gitdir=rtcdir):
							shell.getoutput("git -C %s commit -m test; exit 0" % rtcdir, clean=False)
						print(git_got_changes(gitdir=rtcdir, logical=False))
						return False
					else:
						shouter.shout("\t... verification for baseline in stream %s passed" % self.baseline.name)
						self.verified = True
						self.save()
						baseline = self.baseline
						if not baseline.verified:
							baseline.verified = True
							baseline.save()
						ws_verify.ws_unload(load_dir=rtcdir)
						shell.getoutput("git -C %s add -A; exit 0" % rtcdir, clean=False)
						if git_got_changes(gitdir=rtcdir):
							shell.getoutput("git -C %s commit -m test; exit 0" % rtcdir, clean=False)
						return True
				except Exception as e:
					ws_verify.ws_unload(load_dir=rtcdir)
					shell.getoutput("git -C %s add -A; exit 0" % rtcdir, clean=False)
					if git_got_changes(gitdir=rtcdir):
						shell.getoutput("git -C %s commit -m test; exit 0" % rtcdir, clean=False)
			else:
				shouter.shout("\t!!! baseline in stream %s can not be verified, manual check please" % self.baseline.name)
		else:
			shouter.shout("\t.!. bypassing baseline in stream %s" % self.baseline.name)
		return False

	def update(self,changesets=[]):
		changesetp = None
		numitems = len(changesets)
		for i in range(numitems):
			item = changesets[i]
			if 'uuid' in item.keys() and item['uuid']:
				changeset = None
				created = None
				try:
					changeset,created = ChangeSet.objects.get_or_create(uuid=item['uuid'])
				except ChangeSet.MultipleObjectsReturned:
					for changesett in ChangeSet.objects.filter(uuid=item['uuid']).order_by('sequence'):
						if changesett == self.stream.lastchangeset or changesett in self.stream.lastchangeset.get_ancestors():
							changeset = changesett
					if not changeset:
						changeset,created = ChangeSet.objects.get_or_create(uuid=item['uuid'], sequence=changesett.sequence + 1)
				if created:
					changeset.delete()
					raise ValueError("!!! got new changeset in compare, should've been created earlier, are you refresh the new changes? %s" % item['uuid'])
				if i < 500 or i > numitems - 501:
					shouter.shout("\t... adding changeset %s to baseline in stream %s" % (changeset,self.baseline.uuid))
					self.historys.add(changeset)
				if not changeset.compared:
					shouter.shout("\t... updating changeset %s" % changeset.uuid)
					changeset.comment = item.get('comment','NOCOMMENT')
					author,created = Author.objects.get_or_create(uuid=item['author']['uuid'])
					if created:
						author.name = item['author']['userName']
						author.mail = item['author']['mail']
						author.userid = item['author']['userId']
						author.save()
					changeset.author = author
					if 'workitems' in item.keys():
						for subitem in item['workitems']:
							workitem,created = Workitem.objects.get_or_create(uuid=subitem['uuid'],number=subitem['workitem-number'])
							if created:
								workitem.label = subitem['workitem-label']
								workitem.save()
							changeset.workitems.add(workitem)
					changeset.created = item['creationDate']
					changeset.createtime = string2datetime(changeset.created)
					changeset.compared = True
					changeset.save()
			else:
				raise ValueError("!!! can not find uuid info in the changeset in compare result")
		if self.historys.all():
			self.firstchangeset = self.historys.first()
			self.lastchangeset = self.historys.last()
		if not self.historys_processed:
			self.historys_processed = True
		self.save()

class JsonRecord(models.Model):
	command = models.CharField(max_length=255,unique=True)
	output = models.TextField()
	timestamp = models.DateTimeField(auto_now_add=True,editable=False)

	def __str__(self):
		return self.command
						
class Workspace(models.Model):
	name = models.CharField(max_length=128,unique=True)
	uuid = models.CharField(max_length=64,default='')
	snapshot = models.ForeignKey(Snapshot,null=True)
	baseline = models.ForeignKey(Baseline,null=True)
	component = models.ForeignKey(Component,null=True)
	stream = models.ForeignKey(Stream,null=True)
	timestamp = models.DateTimeField(auto_now_add=True,editable=False)

	class Meta:
		pass

	def __str__(self):
		return self.name

	def ws_list(self,verbose=False,component=None,stream=None):
		if not stream:
			stream = self.stream

		if not component:
			component = self.component
		if not component:
			if self.stream:
				component = self.stream.component
			elif stream:
				component = stream.component
			else:
				pass
		if verbose:
			json_r = json.loads(shell.getoutput("%s list workspaces -r rtc -v -n %s -j -m 2000" % (scmcommand, self.name),clean=False))
		else:
			json_r = json.loads(shell.getoutput("%s list workspaces -r rtc -n %s -j -m 2000" % (scmcommand, self.name),clean=False))
		if json_r:
			if component and stream:
				return list(filter(lambda x: x['name'] == "git_migrate_%s_%s" % ( component.name, re.sub(r' ','',stream.name)), json_r))
		return json_r

	def ws_remove_conflict_merge(self,rtcdir='',changeset=None):
		if rtcdir and changeset:
			os.chdir(rtcdir)
			output = shell.getoutput("%s show history -r rtc -w %s -C %s -j -m 2" % (scmcommand, self.uuid, self.component.uuid),clean=False)
			results = json.loads(output)
			cs_first = None
			if 'changes' in results.keys():
				cs_first = results['changes'][0]
			if cs_first:
				if cs_first['comment'] == "Merges" and cs_first['author'] == RTC_DISPLAY_NAME_IN_HISTORY:
					shouter.shout("\t found merge for conflict resolv in workspace, discard it")
					try:
						shell.execute("cd %s ; %s discard -w %s -o %s" % (rtcdir, scmcommand, self.uuid, cs_first['uuid']))
					except Exception as e:
						shouter.shout("\t.!. problem discarding changeset %s" % cs_first['comment'])
						print(e)
				elif cs_first['uuid'] != changeset.uuid:
					shouter.shout("\t.!. strange, first changeset's uuid is not the same with the changeset migrating")
				else:
					shouter.shout("\t... history first changeset the same with changeset migrating")

	def ws_prepare_initial(self,accept_limit=2000,firstchangeset=None):
		#shouter.shout("\t.!. place holder, implement better here")
		if not self.stream:
			raise ValueError("\t!!! can not prepare initial status, no stream assocciated")
		starting_baseline = None
		starting_baseline_lastchangeset = None
		if not firstchangeset:
			firstchangeset = self.stream.firstchangeset
		bis0 = None
		## if a proper baseline is found, create the workspace based on it, accept or discard corresponding changesets
		for baselineinstream in BaselineInStream.objects.filter(stream=self.stream):
			baseline = baselineinstream.baseline
			if baselineinstream.lastchangeset:
				if not bis0:
					if baselineinstream.lastchangeset.level <= firstchangeset.level:
						bis0 = baselineinstream
				else:
					if baselineinstream.lastchangeset.level <= firstchangeset.level and baselineinstream.lastchangeset.level > bis0.lastchangeset.level :
						bis0 = baselineinstream
		if not bis0:
			for baselineinstream in BaselineInStream.objects.filter(stream=self.stream):
				baseline = baselineinstream.baseline
				if baselineinstream.lastchangeset:
					if not bis0:
						if baselineinstream.lastchangeset.level > firstchangeset.level and baselineinstream.lastchangeset.level < firstchangeset.level + 2000:
							bis0 = baselineinstream
					else:
						if baselineinstream.lastchangeset.level > firstchangeset.level and baselineinstream.lastchangeset.level < bis0.lastchangeset.level :
							bis0 = baselineinstream
		if bis0:
			starting_baseline = bis0.baseline
			starting_baseline_lastchangeset = bis0.lastchangeset

		## otherwise, create empty workspace and accept the changesets
		else:
			queryset_templates =  Baseline.objects.filter(verified=True).filter(level=0).filter(lastchangeset__isnull=False)
			if queryset_templates:
				for qs_template in queryset_templates:
					if not starting_baseline:
						starting_baseline = qs_template
						starting_baseline_lastchangeset = qs_template.lastchangeset
					elif qs_template.lastchangeset.level < firstchangeset.level and qs_template.lastchangeset.level > starting_baseline_lastchangeset.level:
						starting_baseline = qs_template
						starting_baseline_lastchangeset = qs_template.lastchangeset
					else:
						pass
		if starting_baseline and starting_baseline_lastchangeset:
			shouter.shout("\t...found the proper baseline @%g to create the workspace for migration of stream %s" % (starting_baseline_lastchangeset.level,self.stream.name))
			self.baseline = starting_baseline
			self.save()
			self.ws_add_component()
			self.ws_list_component()
			#self.ws_unset_flowtarget()
			#self.ws_list_flowtarget()
			self.ws_set_flowtarget()
			self.ws_list_flowtarget()
			if starting_baseline_lastchangeset.level == firstchangeset.level:
				pass
			elif starting_baseline_lastchangeset.level < firstchangeset.level:
				### baseline and accept some changesets
				if firstchangeset.get_ancestors().filter(level__gt=starting_baseline_lastchangeset.level).count() > accept_limit:
					N = firstchangeset.get_ancestors().filter(level__gt=starting_baseline_lastchangeset.level).count() // accept_limit
					shouter.shout("\t\t.!.!.! ooooooooooops, we have to accept multiple times to prepare workspace for migration, continue?")
					for t in range(N):
						command = "%s accept -c -N -r rtc -t %s --no-merge -o " % (scmcommand, self.uuid)
						for changeset in firstchangeset.get_ancestors().filter(level__gt=starting_baseline_lastchangeset.level)[t * accept_limit:t * accept_limit + accept_limit]:
							command += changeset.uuid + " "
						print(shell.getoutput(command,clean=False))
					command = "%s accept -c -N -r rtc -t %s --no-merge -o " % (scmcommand, self.uuid)
					for changeset in firstchangeset.get_ancestors().filter(level__gt=starting_baseline_lastchangeset.level)[N * accept_limit:]:
						command += changeset.uuid + " "
					command += firstchangeset.uuid
					print(shell.getoutput(command,clean=False))
				else:
					command = "%s accept -c -N -r rtc -t %s --no-merge -o " % (scmcommand, self.uuid)
					for changeset in firstchangeset.get_ancestors().filter(level__gt=starting_baseline_lastchangeset.level):
						command += changeset.uuid + " "
					command += firstchangeset.uuid
					print(shell.getoutput(command,clean=False))
			else:
				### baseline and drop some changesets
				command = "%s discard -N -r rtc -w %s -o " % (scmcommand, self.uuid)
				for changeset in starting_baseline_lastchangeset.get_ancestors().filter(level__gt=firstchangeset.level):
					command += changeset.uuid + " "
				command += starting_baseline_lastchangeset.uuid
				print(shell.getoutput(command,clean=False))
		else:
			shouter.shout("\t...did not find the proper baseline to create the workspace for migration of stream %s" % self.stream.name)
			self.ws_add_component()
			self.ws_list_component()
			self.ws_set_flowtarget()
			self.ws_list_flowtarget()
			if firstchangeset.get_ancestors().filter(level__gt=0).count() > accept_limit:
				N = firstchangeset.get_ancestors().filter(level__gt=0).count() // accept_limit
				shouter.shout("\t\t.!.!.! ooooooooooops, we have to accept multiple times to prepare workspace for migration, continue?")
				for t in range(N):
					command = "%s accept -c -N -r rtc -t %s --no-merge -o " % (scmcommand, self.uuid)
					for changeset in firstchangeset.get_ancestors().filter(level__gt=0)[t * accept_limit:t * accept_limit + accept_limit]:
						command += changeset.uuid + " "
					print(shell.getoutput(command,clean=False))
				command = "%s accept -c -N -r rtc -t %s --no-merge -o " % (scmcommand, self.uuid)
				for changeset in firstchangeset.get_ancestors().filter(level__gt=0)[N * accept_limit:]:
					command += changeset.uuid + " "
				command += firstchangeset.uuid
				print(shell.getoutput(command,clean=False))
				
			else:
				command = "%s accept -c -N -r rtc -t %s --no-merge -o " % (scmcommand, self.uuid)
				for changeset in firstchangeset.get_ancestors().filter(level__gt=0):
					command += changeset.uuid + " "
				command += firstchangeset.uuid
				print(shell.getoutput(command,clean=False))

	def ws_daily_update(self):
		stream = self.stream
		gitbranch = GitBranch.objects.get(name=stream.name)
		if not self.stream or self.snapshot:
			shouter.shout("\t!!! not ready for daily update, please verify")
			raise ValueError("Can not perform daily update yet")
		os.chdir(os.path.join(migration_top,self.component.name,'rtcdir'))
		output = shell.getoutput("lscm show status -j",clean=False)
		items = json.loads(output)
		old_lastchangeset = stream.lastchangeset
		new_lastchangeset = None
		firstitem = True
		changesetp = None
		changeset = None
		for item in items['workspaces'][0]['components'][0]['incoming-changes']:
			if 'uuid' in item.keys():
				changeset,created = ChangeSet.objects.get_or_create(uuid=item['uuid'])
				changeset.comment = item['comment'].strip()
				if changesetp:
					if not changesetp.parent:
						changesetp.parent = changeset
						changesetp.save()
					else:
						if changesetp.parent != changeset:
							raise ValueError("!!!found problem of changeset history, resolve it")
				if created:
					changeset.created = item['modified']
					changeset.createtime = string2datetime(changeset.created)
					changesetp = changeset
					if changeset.uuid in Component.objects.values_list('uuid',flat=True):
						changeset.category = Category.objects.get(name='component')
					changeset.save()
				else:
					changesetp = None
				if firstitem:
					new_lastchangeset = changeset
					changesetp = changeset
					if not changeset.is_leaf_node():
						raise ValueError("Expecting node to be leaf")
#				shouter.shout("\t...changeset level %g  %s -> %s" % (changeset.level, changeset.uuid,changeset.comment))
			firstitem = False
		if new_lastchangeset:
			stream.lastchangeset = new_lastchangeset
			stream.save()
			if changeset and changeset.is_root_node():
				shouter.shout("\t...last changeset %s -> %s" % (changeset.uuid,changeset.comment))
				changeset.parent = old_lastchangeset
				changeset.save()
				shouter.shout("\t...changeset level %g  %s -> %s" % (changeset.level, changeset.uuid,changeset.comment))


	def ws_suspend(self,rtcdir='',changesets=[]):
		shouter.shout("\t...Now it is time to suspend the changesets")
		shouter.shout("\t...stream: %s, snapshot: %s" % (self.stream.name, str(self.snapshot)))
	#	prompt = input("\tpress enter when you finish suspend on the project workspace\n\t# ")
	#	time.sleep(5)
		if changesets:
	#		changesets.reverse()
			command = "%s suspend -r rtc -d %s -o -w %s" % (scmcommand, rtcdir, self.uuid)
			command_args = ''
			for changeset in changesets:
				command_args += ' ' + changeset.uuid
			print(shell.getoutput(command + command_args, clean=False))

	def ws_resume(self,use_accept=False):
		rtcdir = os.path.join(migration_top,self.component.name,'rtcdir',re.sub(r' ','',self.stream.name))
		json_compress_changesets = os.path.join(settings.BASE_DIR,'tmp',self.component.name,"json_compress_changesets")
		compress_changesets = []
		compress_changesets2 = []
		if os.path.exists(json_compress_changesets):
			with open(json_compress_changesets,'r') as f:
				compress_changesets = json.load(f)
		shouter.shout("\tNow it is time to resume the changesets")
		shouter.shout("\t...stream: %s, snapshot: %s" % (self.stream.name, str(self.snapshot)))
		os.chdir(rtcdir)
		pushnum = 1
		## remove snapshot based part, do not keep them
		if self.stream and self.stream.lastchangeset:
			shouter.shout("\t...performing stream based migration")
			bis_list = list(BaselineInStream.objects.filter(stream=self.stream))
			stream_list = sorted(list(self.stream.children.all()), key = lambda x: x.firstchangeset.level)
			qs_migrated = self.stream.lastchangeset.get_ancestors().filter(migrated=True).exclude(level=0).order_by('-createtime')
			if qs_migrated:
				cs_create_time = qs_migrated[0].createtime
			else:
				cs_create_time = datetime.datetime(1980,1,1)

			for changeset in list(self.stream.lastchangeset.get_ancestors().filter(migrated=False)) + [self.stream.lastchangeset]:
				bis_list_filtered = list(filter(lambda x: x.baseline and x.lastchangeset == changeset , bis_list))
				stream_list_filtered = list(filter(lambda x: x.firstchangeset == changeset, stream_list))
				cs_create_time_old = cs_create_time
				checkpoint = False

				if stream_list_filtered or bis_list_filtered:
					checkpoint = True
				if not changeset.compared:
					shouter.shout("\t!!! does not have information for changeset %s like comments or workitems, pleaset update it" % changeset.uuid)
					sys.exit(9)
				if changeset.createtime > cs_create_time:
					cs_create_time = changeset.createtime
				else:
					if SQUASH_AGGRESIVE:
						shouter.shout("\t.!. changeset %g %s is squashable changesets, fast forwarding ..." % (changeset.level, changeset.uuid))
						if not checkpoint:
							compress_changesets.append(changeset.uuid)
							continue
					else:
						shouter.shout("\t.!. changeset %g %s is squashable, but let us try our best to keep the history ..." % (changeset.level, changeset.uuid))
						if ChangeSet.objects.filter(uuid=changeset.uuid).count() > 1:
							if len(compress_changesets) < SQUASH_MAX_TRY:
								shouter.shout("\t.!..!. multiple delivered changeset #%g: let us try our best to keep the history up to 10 ..." % (len(compress_changesets)))
							else:
								shouter.shout("\t.!..!. multiple delivered changesets more than %g, compress it ..." % SQUASH_MAX_TRY)
								if not checkpoint:
									compress_changesets.append(changeset.uuid)
									continue
						else:
							shouter.shout("\t.!..!. unique changeset, try to keep the history ...")
				if checkpoint:
					self.ws_remove_conflict_merge(rtcdir=rtcdir,changeset=changeset)
				compress_changesets2 = changeset.resume(self,use_accept=use_accept,rtcdir=rtcdir,compress_changesets=compress_changesets,checkpoint=checkpoint)
				if changeset.createtime > cs_create_time_old and changeset.level > 10 and changeset.parent.createtime < cs_create_time_old:
					self.ws_remove_conflict_merge(rtcdir=rtcdir,changeset=changeset)

				if compress_changesets2 != compress_changesets:
					shouter.shout(".!. detected changeset compress, pay attention please")
					compress_changesets = compress_changesets2.copy()
					if not os.path.exists(os.path.dirname(json_compress_changesets)):
						os.makedirs(os.path.dirname(json_compress_changesets))
					with open(json_compress_changesets,'w') as f:
						json.dump(compress_changesets,f)
				changeset.refresh_from_db()
				if stream_list_filtered:
					shell.execute("git -C %s push" % rtcdir)
					for s in stream_list_filtered:
						s.refresh_from_db()
						print(subprocess.check_output("git -C %s checkout -b %s" % (rtcdir, re.sub(r' ','',s.name)),shell=True).decode())
						shell.execute("git -C %s checkout %s" % (rtcdir,re.sub(r' ','',self.stream.name)))
						print(subprocess.check_output("git -C %s push origin :refs/heads/%s; echo test only ;git -C %s push origin %s:refs/heads/%s" % (rtcdir, re.sub(r' ','',s.name), rtcdir, re.sub(r' ','',s.name), re.sub(r' ','',s.name)), shell=True).decode())
						shouter.shout("\t... verifying branching point for %s in sync %s <=> %s" % (s.name, changeset.uuid, changeset.commit.commitid))
						validated = s.validate_branchingpoint()
						if not validated:
							shouter.shout("\t.!. branching point validation failed")
							raise ValueError("Validation failed")
						else:
							shouter.shout("\t... branching point for %s VALIDATED\n" % s.name)
				if bis_list_filtered:
					shell.execute("git -C %s push" % rtcdir)
					for bis in bis_list_filtered:
						bis.refresh_from_db()
						shouter.shout("\t... verifying baseline in stream %s (%s)" % (bis.baseline.name, bis.baseline.comment))
						validated = bis.validate_baseline()
						if not validated:
							shouter.shout("\t.!. baseline in stream validation failed")
							raise ValueError("Validation failed")
						else:
							shouter.shout("\t... baseline in stream VALIDATED\n")
				os.chdir(rtcdir)
				pushnum += 1
				if pushnum == PUSHLIMIT:
					pushnum = 1
					shell.execute("git -C %s push" % rtcdir)
					if True:
						shouter.shout("\t...offer a chance to break or continue")
						time.sleep(5)
				shouter.shout("\tnext:\tpushnum = %g ; level = %g" % (pushnum, changeset.level))
			shell.execute("git -C %s push" % rtcdir)
			#shell.execute("git -C %s push --tags" % rtcdir)
			stream = self.stream
			stream.migrated = True
			stream.save()
		else:
			raise ValueError("workspace can not be resumed, check please")

	def ws_history_changesets(self,file_path=None):
		shouter.shout("\t...verify history is correct by history command")
		changesetp = None
		if file_path and os.path.exists(file_path):
			total = 0
			with open(file_path,'r') as f:
				linef = f.readline()
				uuid = re.sub(r'.*com.ibm.team.scm.ChangeSet/|.Workspace=.*','',linef.strip())
				changesetf = ChangeSet.objects.get(uuid=uuid)
				changesetp = changesetf
				total += 1
				if self.snapshot:
					snapshot = self.snapshot
					snapshot.lastchangeset = changesetf
					snapshot.changesets_listed = True
					snapshot.save()
					if snapshot.baselines.all():
						baseline = snapshot.baselines.all()[0]
						baseline.lastchangeset = changesetf
						baseline.save()
				else:
					stream = self.stream
					stream.lastchangeset = changesetf
					stream.save()
				for line in f:
					uuid = re.sub(r'.*com.ibm.team.scm.ChangeSet/|.Workspace=.*','',line.strip())
					changeset = ChangeSet.objects.get(uuid=uuid)
					if changesetp:
						if changesetp.parent != changeset:
							raise ValueError("!!!found problem of changeset history, resolve it")
						total += 1
						changesetp = changeset
					else:
						raise ValueError("Did not find the previous changeset")
			return total
		command = "lscm show history -r rtc -w %s -m 1000 -j -C %s" % (self.uuid, self.stream.component.uuid)
		output = shell.getoutput(command, clean=False)
		items = json.loads(output)
		if 'changes' in items.keys():
			changesetf,created = ChangeSet.objects.get_or_create(uuid=items['changes'][0]['uuid'])
			if created:
				shouter.shout("!!! got issue, created new changeset while verify history")
				sys.exit(11)
			changesetp = changesetf
			if self.snapshot:
				snapshot = self.snapshot
				snapshot.lastchangeset = changesetf
				snapshot.changesets_listed = True
				snapshot.save()
				if snapshot.baselines.all():
					baseline = snapshot.baselines.all()[0]
					baseline.lastchangeset = changesetf
					baseline.save()
			else:
				stream = self.stream
				stream.lastchangeset = changesetf
				stream.save()

			for item in items['changes'][1:]:
				if 'uuid' in item.keys():
					changeset,created = ChangeSet.objects.get_or_create(uuid=item['uuid'])
					if changesetp:
						if changesetp.parent != changeset:
							raise ValueError("!!!found problem of changeset history, resolve it")
					if created:
						shouter.shout("!!! got issue, created changeset whlie verify history")
						sys.exit(11)
					else:
						changesetp = changeset
				else:
					raise ValueError("did not find changesets uuid")
		else:
			raise ValueError("did not find changesets associated with workspace %s" % self.name)
		return len(items['changes']) 
	def ws_list_changesets(self,maximum=10):
		total = 0
		command = "lscm list changesets -r rtc -w %s -m %g -j" % (self.uuid,maximum)
		output = shell.getoutput(command, clean=False)
		items = json.loads(output)
		changesetp = None
		if 'changes' in items.keys() and items['changes']:
			changesetf,created = ChangeSet.objects.get_or_create(uuid=items['changes'][0]['uuid'])
			if created:
				changesetf.created = items['changes'][0]['modified']
				changesetf.createtime = string2datetime(changesetf.created)
				#changesetf.delivered = items['changes'][0]['date-added']
				#changesetf.delivertime = string2datetime(changesetf.delivered)
				changesetf.comment =  items['changes'][0]['comment'].strip()
				if changesetf.uuid in Component.objects.values_list('name',flat=True):
					changesetf.category = Category.objects.get(name='component')
				changesetf.save()
				changesetp = changesetf 

			if self.snapshot:
				snapshot = self.snapshot
				snapshot.lastchangeset = changesetf
				snapshot.save()
				#if snapshot.baselines.all():
				#	baseline = snapshot.baselines.all()[0]
				#	baseline.lastchangeset = changesetf
				#	baseline.save()
			if self.baseline:
				baseline = self.baseline
				baseline.lastchangeset = changesetf
				baseline.save()

			if self.stream:
				stream = self.stream
				stream.lastchangeset = changesetf
				stream.save()

			for item in items['changes'][1:]:
				if 'uuid' in item.keys():
					changeset,created = ChangeSet.objects.get_or_create(uuid=item['uuid'])
					if changesetp:
						if not changesetp.parent:
							changesetp.parent = changeset
							changesetp.save()
						elif changesetp.parent != changeset:
							shouter.shout("!!!found problem of changeset history, resolve it")
							input("press any key to continue or break to inspect")
						else:
							#shouter.shout("...found parent changeset %s" % changeset.uuid)
							pass
					if created:
						changeset.created = item['modified']
						changeset.createtime = string2datetime(changeset.created)
						#changeset.delivered = item['date-added']
						#changeset.delivertime = string2datetime(changeset.delivered)
						changeset.comment = item['comment'].strip()
						shouter.shout("\tfound new changeset %s" % changeset.comment)
						if changeset.uuid in Component.objects.values_list('uuid',flat=True):
							changeset.category = Category.objects.get(name='component')
						changeset.save()
					else:
						#shouter.shout("\tfound parent changeset %s" % changeset.comment)
						pass
					changesetp = changeset
				else:
					raise ValueError("did not find changesets uuid")
		else:
			shouter.shout("did not find changesets associated with workspace %s" % self.name)
		return len(items['changes']) 

	def ws_update(self,stream=None,component=None):
		if not self.uuid:
			if self.ws_exist(stream=stream,component=component):
				self.uuid = self.ws_list(stream=stream,component=component)[0]['uuid']
				self.save()
		else:
			if not self.ws_exist(stream=stream,component=component):
				self.uuid = ''
				self.save()
			else:
				if self.uuid != self.ws_list(stream=stream,component=component)[0]['uuid']:
					self.uuid = self.ws_list(stream=stream,component=component)[0]['uuid']
					self.save()

	def ws_exist(self,component=None,stream=None):
		if not stream:
			stream = self.stream
		if not component:
			component = self.component
		if not component:
			if self.stream:
				component = self.stream.component
			elif stream:
				component = stream
			else:
				pass
		return len(self.ws_list(component=component,stream=stream))

	def ws_compare(self,to_snapshot=None,from_snapshot=None):
		if self.stream:
			if self.snapshot:
				if self.snapshot.baselines.all():
					snapshot = self.snapshot
					baseline = snapshot.baselines.all()[0]
					command = "%s compare workspace %s baseline %s -r rtc -I sw -f i -D 'yyyy-MM-dd HH:mm:ss' -j" % (scmcommand, self.name, baseline.uuid)
					snapshot.changesets_compared = True
					snapshot.save()
				else:
					raise ValueError("!!! Can not compare when snapshot does not have a baseline associated")
			else:
#				command = "%s compare workspace %s stream %s -r rtc -I sbw -f i -D \"yyyy-MM-ddTHH:mm:ss\" -j" % (scmcommand, self.name, self.stream.uuid)
#				command = "scm compare -r rtc -I sbw -f i -D 'yyyy-MM-dd HH:mm:ss' -j workspace %s snapshot %s" % (self.name, "snapshot_after_format_conversion")
				command = "%s compare -r rtc -I sw -f i -D 'yyyy-MM-dd HH:mm:ss' -j workspace %s stream %s" % (scmcommand, self.name, self.stream.uuid)
			output = shell.getoutput(command, clean=False)
#			output = shell.getoutput("scm compare -r rtc -I sbw -f i -D \"yyyy-MM-dd HH:mm:ss\" -j workspace %s snapshot %s" % (self.name, "ego_ego_mainline_rtc_to_git_20150612"),clean=False)
#			output = shell.getoutput("%s compare -r rtc -I sbw -f i -D \"yyyy-MM-dd HH:mm:ss\" -j workspace %s snapshot %s" % (scmcommand, self.name, "snapshot_after_format_conversion"),clean=False)
			items = json.loads(output)
			changesetp = None
			if not 'changesets' in items['direction'][0]['components'][0].keys():
				shouter.shout("\t.!. did not find incoming changeset")
				sys.exit(10)
			for item in items['direction'][0]['components'][0]['changesets']:
				if 'uuid' in item.keys() and item['uuid']:
					changeset,created = ChangeSet.objects.get_or_create(uuid=item['uuid'])
					if created:
						raise ValueError("!!! got new changeset in compare, rerun list changeset please")
					if 'comment' in item.keys() and item['comment']:
						changeset.comment = item['comment'].strip()
					else:
						shouter.shout("!!! got changeset with empty comment %s" % changeset.uuid)
						changeset.comment = "empty-comment"
					author,created = Author.objects.get_or_create(uuid=item['author']['uuid'])
					if created:
						author.name = item['author']['userName']
						author.mail = item['author']['mail']
						author.userid = item['author']['userId']
						author.save()
					changeset.author = author
					if 'workitems' in item.keys():
						for subitem in item['workitems']:
							workitem,created = Workitem.objects.get_or_create(uuid=subitem['uuid'],number=subitem['workitem-number'])
							if created:
								workitem.label = subitem['workitem-label']
								workitem.save()
							changeset.workitems.add(workitem)
					changeset.created = item['creationDate']
					changeset.createtime = string2datetime(changeset.created)
					changeset.save()
					if changesetp:
						if changesetp.parent and changesetp.parent.category.name == 'component':
							changesetp = changesetp.parent
						if changesetp.parent != changeset:
							raise ValueError("Found strange changeset, notice please")
				else:
					raise ValueError("!!! can not find uuid info in the changeset in compare result")
		else:
			raise ValueError("!!! Can not compare when workspace does not have a stream associated")
	def ws_create(self):
		if self.snapshot:
			shouter.shout("\t ... created snapshot based workspace")
			info = json.loads(shell.getoutput("%s create workspace -r rtc -j --snapshot %s %s" % (scmcommand, self.snapshot.uuid, self.name),clean=False))
		elif self.stream:
			shouter.shout("\t ... created stream based workspace")
			info = json.loads(shell.getoutput("%s create workspace -r rtc -j --stream %s %s" % (scmcommand, self.stream.uuid, self.name),clean=False))
		else:
			shouter.shout("\t ... created empty workspace")
			info = json.loads(shell.getoutput("%s create workspace -r rtc -j --empty %s" % (scmcommand, self.name),clean=False))

		if type(info) == type({}) and 'name' in info.keys() and 'uuid' in info.keys() and info['name'] == self.name:
			self.uuid = info['uuid']
			self.save()
			if self.stream:
				shouter.shout("\t ... set flow target for workspace %s to stream %s" % (self.name,self.stream.name))
				self.ws_set_flowtarget()
			elif self.component:
				shouter.shout("\t ... adding component to workspace %s" % self.name)
				self.ws_add_component()
			else:
				pass
		else:
			shouter.shout("\t!!! got issue creating workspace %s" % self.name)

	def ws_load(self,load_dir='.'):
		if self.uuid:
			try:
				return shell.getoutput("cd %s ; %s load -r rtc --all --force %s" % (load_dir,scmcommand,self.uuid),clean=False)
			except subprocess.CalledProcessError as lscmservice:
				if lscmservice.returncode == 243:
					rtclogin_restart()
					return shell.getoutput("cd %s ; %s load -r rtc --all --force %s" % (load_dir, scmcommand, self.uuid),clean=False)
				else:
					raise ValueError("!!! Got unexpected load error")
		else:
			shouter.shout("\t!!! can not load, check workspace please")
			return "no uuid to load"

	def ws_unload(self,load_dir='.'):
		if self.uuid:
			return shell.getoutput("%s unload -d %s -r rtc -i -N -w %s -C %s" % (scmcommand,load_dir,self.uuid,self.component.uuid),clean=False)
		else:
			shouter.shout("\t!!! can not unload, check workspace please")
			return "no uuid to load"

	def ws_delete(self,stream=None,component=None):
		if self.ws_exist(stream=stream,component=component):
			self.ws_update(stream=stream,component=component)
		if self.uuid:
			shell.execute("%s delete workspace -r rtc  %s" % (scmcommand,self.uuid))
			if not self.ws_exist(stream=stream,component=component):
				if self.uuid:
					self.uuid = ''
					self.save()
		else:
			shell.execute("%s delete workspace -r rtc  %s" % (scmcommand,self.name))
			shouter.shout("\t.!. tried to delete with workspace name, check workspace please")
		self.ws_update(stream=stream,component=component)

	def ws_list_flowtarget(self):
		if self.uuid:
			shell.execute("%s list flowtargets -r rtc %s" % (scmcommand,self.uuid))

	def ws_set_flowtarget(self,target=0):
		if self.component:
			if self.uuid:
				if target:
					if hasattr(target,'uuid'):
						shell.execute("%s set flowtarget -C %s -r rtc %s %s" % (scmcommand, self.component.uuid, self.uuid, target.uuid))
					elif hasattr(target,'name'):
						shell.execute("%s set flowtarget -C %s -r rtc %s %s" % (scmcommand, self.component.uuid, self.uuid, target.name))
					else:
						shouter.shout("\t.!. did you specified the correct target?")
						pass
				elif self.stream:
					shell.execute("%s set flowtarget -C %s -r rtc %s %s" % (scmcommand, self.component.uuid, self.uuid, self.stream.uuid))
				else:
					shouter.shout("no target to set for flow")
			elif self.name:
				if target:
					if hasattr(target,'uuid'):
						shell.execute("%s set flowtarget -C %s -r rtc %s %s" % (scmcommand, self.component.uuid, self.name, target.uuid))
					elif hasattr(target,'name'):
						shell.execute("%s set flowtarget -C %s -r rtc %s %s" % (scmcommand, self.component.uuid, self.name, target.name))
					else:
						shouter.shout("\t.!. did you specified the correct target?")
				elif self.stream:
					shell.execute("%s set flowtarget -C %s -r rtc %s %s" % (scmcommand, self.component.uuid, self.uuid, self.stream.uuid))
				else:
					shouter.shout("no target to set for flow")
			else:
				pass

	def ws_unset_flowtarget(self):
		shell.execute("%s unset flowtarget -r rtc %s" % (scmcommand,self.uuid))
		
	def ws_list_component(self):
		if self.uuid:
			shell.execute("%s list components -r rtc %s" % (scmcommand,self.uuid))

	def ws_set_component(self):
		if self.uuid and self.stream and self.baseline:
			shell.execute("%s set component -r rtc -o -b %s %s stream %s %s" % (scmcommand, self.baseline.uuid, self.uuid, self.stream.uuid, self.baseline.component.uuid))
		elif self.uuid and self.stream and self.snapshot and self.snapshot.baselines.all().count() == 1:
			baseline = self.snapshot.baselines.all()[0]
			shell.execute("%s set component -r rtc -o -b %s %s stream %s %s" % (scmcommand, baseline.uuid, self.uuid, self.stream.uuid, baseline.component.uuid))
		else:
			shouter.shout("no snapshot bounded")
	def ws_add_component(self):
		if self.uuid and self.component and self.baseline:
			shell.execute("%s add component -r rtc -b %s %s %s" % (scmcommand, self.baseline.uuid, self.uuid, self.component.uuid))
		elif self.uuid and self.component:
			shell.execute("%s add component -r rtc %s %s" % (scmcommand, self.uuid, self.component.uuid))
		else:
			shouter.shout("no component bounded")
	def ws_last_changeset(self,maximum=1):
		if self.uuid and self.ws_exist():
			command = "%s list changesets -r rtc -w %s -m %g -j" % (scmcommand, self.uuid, maximum)
			output = shell.getoutput(command, clean=False)
			items = json.loads(output)
			return items['changes'][0]['uuid']
		else:
			return "doesnotexist"
