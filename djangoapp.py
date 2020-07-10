#!/usr/bin/env python3

#from __future__ import generators
import os, sys, re, time
import subprocess
import shouter, shell
import json
import pprint
from optparse import OptionParser
from django.core.mail import send_mail
import imp

DJANGOPATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(DJANGOPATH)
os.environ["DJANGO_SETTINGS_MODULE"] = "gitrtc.settings"

parser = OptionParser()
parser.add_option("--verbose",action="store_true",dest="verbose",help="seeing more info")
parser.add_option("--infoinit",help="information initialize for rtc", action="store_true")
parser.add_option("--infoupdate",help="information update about a component and its streams", action="store_true")
parser.add_option("--incremental",help="information update picking up new changesets and compare them", action="store_true")
parser.add_option("--shortcut_analyze",help="information update picking up new changesets and compare them", action="store_true")
parser.add_option("--branchfurther",help="to further determine branching when multiple stream branches at the same changeset", action="store_true")
parser.add_option("--streamparent", help="specify the stream id that you want to determine branch as parent",action="store",type="string")
parser.add_option("--infoshow",help="information show about a component and its streams", action="store_true")
parser.add_option("--showstream",help="show information about stream", action="store_true")
parser.add_option("--inforeport",help="report information about component and streams", action="store_true")
parser.add_option("--withchangesets",help="write information about stream to file including changesets", action="store_true")
parser.add_option("--writehistory",help="write stream history to file", action="store_true")
parser.add_option("--infoverify",help="verify stream with git branch making sure the baselines in stream is correct", action="store_true")
parser.add_option("--withbaselines",help="write or verify stream with baselines in stream", action="store_true")
parser.add_option("--withbranchingpoints",help="verify branching points of a stream in streams specified", action="store_true")
parser.add_option("--withfirstbaselineinstream",help="print first baseline in stream to help relationship", action="store_true")
parser.add_option("--withbranchingpoint",help="print the branching point", action="store_true")
parser.add_option("--migrate",help="migrate base stream", action="store_true")
parser.add_option("--tagbaselines",help="sync rtc baselines to git tags", action="store_true")
parser.add_option("--allstreams",help="migrate all rest streams", action="store_true")
parser.add_option("--withrelogin",help="migrate a stream with restart the lscm daemons, necessary if yo delete local workspace", action="store_true")
parser.add_option("--withvalidation",help="migrate a stream with validation of baselines and branching points", action="store_true")
parser.add_option("--streambase", help="specify the stream name",dest="stream",action="store",type="string")
parser.add_option("--component", help="specify the component name",action="store",type="string")
parser.add_option("--recordpath", help="specify the path where records were writen",action="store",type="string")
parser.add_option("--levelrange", help="specify changeset level range lists to show in inforeport",action="store",type="string")
parser.add_option("--levelinterval", help="specify changeset level half diameter to show in inforeport",action="store",type="string")
parser.add_option("--sleepinterval", help="specify time to sleep for internal signals",action="store",type="string")
parser.add_option("--streams", help="specify streams for infoupdate or inforeport",action="store",type="string")
(options,args) = parser.parse_args()
#DEFAULT_LEVEL_INDICATOR = getattr(settings, 'MPTT_DEFAULT_LEVEL_INDICATOR', '---')
def stream_rebuild_tree():
	if os.path.exists("/tmp/.stream_rebuild"):
		shouter.shout("\t...rebuilding stream tree")
		Stream.objects.rebuild()
		shell.execute("rm -f /tmp/.stream_rebuild; exit 0")

if __name__ == '__main__':
#	cmd = sys.argv.pop(1)
	if not os.path.exists(os.path.join(DJANGOPATH,'tmp')):
		os.mkdir(os.path.join(DJANGOPATH,'tmp'))
	try:
		output = shell.getoutput("which lscm",clean=False)
		if not re.match(r'.*scm',output):
			shouter.shout("\t!!! I did not find lscm command, did you install scmtools and have it in your PATH env?")
			sys.exit(9)
	except Exception as e:
		shouter.shout("\t!!! I did not find lscm command, did you install scmtools and have it in your PATH env?")
		sys.exit(9)
	# shen added options.tagbaselines
	if options.infoinit or options.infoshow or options.infoupdate or options.inforeport or options.infoverify or options.migrate or options.tagbaselines:
		component_name = options.component
		if not component_name:
			shouter.shout("\t!!!We will do component based migrations, it is required to specify the component with option --component=component_string")
			sys.exit(9)
		import local_settings
		stream_based = local_settings.STREAM_BASED
		if not stream_based:
			stream_based = True
		levelinterval = local_settings.levelinterval
		if options.levelinterval:
			levelinterval = int(options.levelinterval)
		if local_settings.DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
			while local_settings.DATABASES['default']['NAME'] != os.path.join(local_settings.BASE_DIR,"db.%s.sqlite3" % re.sub(r' ','',component_name)):
				shouter.shout("\t... you are using sqlite3 as database engine, setting db file as db.%s.sqlite3" % re.sub(r' ','',component_name))
				# shen commented out one line
				# shen input("any key to continue or break")
				print(subprocess.check_output("sed -e \"s/\(^[[:space:]]*\)\'NAME\'.*/\\1\'NAME\': os.path.join(BASE_DIR, \'db.%s.sqlite3\')/\" local_settings.py > /tmp/local_settings.py; cat /tmp/local_settings.py > local_settings.py; cat local_settings.py | grep -v \"^#\" | grep -v \"^$\" ;  exit 0" % (re.sub(r' ','',component_name)),shell=True).decode())
				imp.reload(local_settings)
		elif local_settings.DATABASES['default']['ENGINE'] == 'django.db.backends.mysql':
			if local_settings.DATABASES['default']['NAME'] != re.sub(r' ','',component_name):
				shouter.shout("\t... you are using mysql as database engine, setting mysql db as %s" % re.sub(r' ','',component_name))
				shouter.shout("\t... if you did not create this database yet, create it now with proper permissions")
				input("any key to continue or break")
				print(subprocess.check_output("sed -e \"s/\(^[[:space:]]*\)\'NAME\'.*/\\1\'NAME\': \'%s\',/\" local_settings.py > /tmp/local_settings.py; cat /tmp/local_settings.py > local_settings.py; cat local_settings.py | grep -v \"^#\" | grep -v \"^$\" ;  exit 0" % (re.sub(r' ','',component_name)),shell=True).decode())
		else:
			raise ValueError("!!! only sqlite and mysql engine is allowed here")
#		sys.exit(9)
		levelrange = local_settings.levelrange
		streams = local_settings.streams
		if options.levelrange:
			levelrange = json.loads(options.levelrange)
		if options.streams:
			streams = json.loads(options.streams)
		import django
		django.setup()
		from rtc.models import *
		from functions import *
		from django.conf import settings
		db = settings.DATABASES['default']
		try:
			ccs,creatd = Category.objects.get_or_create(name='changeset')
			cco,created = Category.objects.get_or_create(name='component')
			cst,created = Category.objects.get_or_create(name='stream')
			cbl,created = Category.objects.get_or_create(name='baseline')
		except Exception as e:
			shouter.shout("\t... try to migrate database schema")
			try:
				print(subprocess.check_output("%s migrate" % os.path.join(settings.BASE_DIR,'manage.py'),shell=True).decode())
			except subprocess.CalledProcessError:
				shouter.shout("\t!!! schema migration failed, did you create your database and got the permissions?")
				sys.exit(9)
		django.setup()
		from django.contrib.auth.models import User
		admin, created = User.objects.get_or_create(username="admin", email="admin@email.com")
		if created:
			shouter.shout("\t... created admin user as admin/admin")
			admin.set_password("admin")
			admin.save()
		if not ProjectArea.objects.all():
			shouter.shout("\t... try to load fixtures")
			if os.path.exists(os.path.join(settings.BASE_DIR,'rtc','fixtures','infoinit.json')):
				print(subprocess.check_output("%s loaddata infoinit" % os.path.join(settings.BASE_DIR,'manage.py'),shell=True).decode())
			else:
				if not options.infoinit:
					shouter.shout("\t!!! failed to load fixtures")
					shouter.shout("\t!!! you need run the initialization first with --infoinit")
					sys.exit(5)
		shouter.shout("\t...try to migrate database schema changes if any")
		print(subprocess.check_output("%s migrate rtc" % os.path.join(settings.BASE_DIR,'manage.py'),shell=True).decode())
		rtclogin()
		verbose = False
		optionsstream = 'specify_component_name'
		if options.stream:
			optionsstream = options.stream
		else:
			shouter.shout("\t.!.you need specify a  stream name with --streambase")
			shouter.shout("\t.!.use %s" % optionsstream)
		try:
			component0 = Component.objects.get(name=component_name)
			gitdir = os.path.join(migration_top,component0.name,'gitdir')
			RTCDIR = os.path.join(migration_top,component0.name,'rtcdir')
		except Component.DoesNotExist:
			if not options.infoinit:
				shouter.shout("\t !!! component %s not found" % component_name)
				sys.exit(9)
		try:
			stream0 = Stream.objects.get(name=optionsstream)
			list_streams= []
			if streams:
				for si in streams:
					if si != stream0.id:
						list_streams.append(Stream.objects.get(id=si))
			else:
				list_streams = list(Stream.objects.filter(component=component0).exclude(id=stream0.id))
		except Stream.DoesNotExist:
			if not options.infoinit:
				shouter.shout("\t !!! some stream name or id you specified do not exist")
				sys.exit(9)
		if options.verbose:
			verbose = True

	if options.showstream:
		try:
			stream = Stream.objects.get(name=optionsstream)
			shouter.shout("snapshots and baselines inside stream:")
			for snapshot in stream.snapshots.all():
				if not snapshot.createtime:
					snapshot.update_time()
				for baseline in snapshot.baselines.all():
					if not baseline.createtime:
						baseline.update_time()
			for snapshot in stream.snapshots.all().order_by('-createtime'):
				shouter.shout("\tsnapshot: %s(%s)" % (snapshot.name,snapshot.comment))
				for otherstream in snapshot.stream_set.all().exclude(uuid=stream.uuid):
					shouter.shout("\t---appear also in stream: %s" % otherstream.name)
				for baseline in snapshot.baselines.all().order_by('-createtime'):
					shouter.shout("\t...baseline: %s | %s(%s)" % (baseline.uuid,baseline.name,baseline.comment))
					for othersnapshot in baseline.snapshot_set.all().exclude(uuid=snapshot.uuid):
						shouter.shout("\t...---appear also in snapshot: %s" % othersnapshot.name)
		except Stream.DoesNotExist:
			shouter.shout("\t!!! stream you specified does not exist")
	elif options.infoverify:
		sorted_streams = []
		if options.allstreams:
			filtered_streams = list(filter(lambda x: x.lastchangeset.get_ancestors(include_self=True).filter(migrated=True),list(Stream.objects.filter(component=component0).exclude(id=stream0.id))))
			sorted_streams = sorted(filtered_streams, key = lambda s: s.level)
		elif options.streams:
			filtered_streams = list(filter(lambda x: x.lastchangeset.get_ancestors(include_self=True).filter(migrated=True),list_streams))
			sorted_streams = sorted(filtered_streams, key = lambda s: s.level)
		else:
			pass
		sorted_streams.insert(0,stream0)

		for stream in sorted_streams:
			stream.refresh_from_db()
			all_verifed = True
			bis_list = list(BaselineInStream.objects.filter(stream=stream))
			child_stream_list = sorted(list(stream.children.all()), key = lambda x: x.firstchangeset.level)
			shouter.shout("\t ... verifying baselines for stream %s" % stream.name)
			if stream.verified:
				shouter.shout("\t... baselines in stream %s has already been verified" % stream.name)
			else:
				for bis in bis_list:
					bis.refresh_from_db()
					if bis.verified:
						shouter.shout("\t... baseline in stream %s had been verified earlier" % bis.baseline.name)
						continue
					verified = bis.validate_baseline()
					if not verified:
						all_verified = False
			#shouter.shout("\t ... verifying 10 random changesets")
			if all_verifed:
				stream.verified = True
				stream.save()

			if options.withbranchingpoints:
				for ss in child_stream_list:
					ss.refresh_from_db()
					if ss.validated:
						shouter.shout("\t... branching point %s has been already VALIDATED" % ss.name)
					else:
						validated = ss.validate_branchingpoint()
						if not validated:
							shouter.shout("\t.!. branching point validation failed for stream %s" % ss.name)
							raise ValueError("Validation failed")
						else:
							shouter.shout("\t... branching point for %s VALIDATED\n" % ss.name)
	elif options.infoshow:
		sync_streams(component_name=component_name,short_cut=True)
		stream_rebuild_tree()
		try:
			stream0 = Stream.objects.get(name=optionsstream)
			list_streams = []
			if streams:
				for si in streams:
					if si != stream0.id:
						list_streams.append(Stream.objects.get(id=si))
			else:
				list_streams = list(Stream.objects.filter(component=component0).exclude(id=stream0.id))
		except Stream.DoesNotExist:
			shouter.shout("\t !!! some stream name or id you specified do not exist")
			sys.exit(9)
		try:
			filtered_streams = list(filter(lambda x: x.history_updated,list_streams))
			sorted_streams = sorted(filtered_streams, key = lambda s: s.lastchangeset.get_ancestors(include_self=True).count(), reverse = True)
			#sorted_streams = sorted(streams, key = lambda s: s.historys.count(), reverse = True)
			sorted_streams.insert(0,stream0)
			levels = [0]
			if stream0.firstchangeset:
				levels = list(set(stream0.firstchangeset.get_descendants().values_list('level',flat=True)))
			print("REPORTING")
			print("\tfor rtc:")
			print("\t\tTotal projectareas: %g" % ProjectArea.objects.count())
			print("\t\tTotal components: %g" % Component.objects.count())
			print("\t\tTotal streams: %g" % Stream.objects.count())
			print("\tfor component %s:" % component_name)
			if stream0.firstchangeset:
				print("\t\tTotal changesets: %g" % stream0.firstchangeset.get_descendant_count())
			print("\t\tTotal streams: %g" % Stream.objects.filter(component__name=component_name).count())
			print('-' * (8 + len(sorted_streams) * 32))
			print("stream_name".ljust(64) + "stream_id (range)")
			for stream in [stream0] + list_streams:
				stream_string = ("%s%s" % (settings.MPTT_DEFAULT_LEVEL_INDICATOR * stream.level, stream.name)).ljust(64)
				if stream.firstchangeset and stream.lastchangeset:
					stream_string += "%-5g(%5g-%-5g)" % (stream.id, stream.firstchangeset.level,stream.lastchangeset.level)
				elif stream.lastchangeset:
					stream_string += "%-5g(%5g-%-5g)" % (stream.id, stream.lastchangeset.get_ancestors(include_self=True).first().level,stream.lastchangeset.level)
				else:
					stream_string += "%-18g" % (stream.id)
				print(stream_string)
			if options.writehistory:
				print('-' * 128)
				for stream in [stream0] + list_streams:
					stream_string = "%s" % stream.name.ljust(64)
					stream_string += os.path.join('tmp',"history_%s" % stream.name)
					print(stream_string)
					with open(os.path.join(settings.BASE_DIR,'tmp',"history_%s" % stream.name),'w') as f:
						if stream.lastchangeset:
							for c in stream.lastchangeset.get_ancestors(include_self=True):
								f.write("%s\n" % c.uuid)
				print('-' * 128)
			if options.withchangesets:
				print('-' * (8 + len(sorted_streams) * 32))
				stream_string = 'chg\stm'.ljust(8)
				for stream in sorted_streams:
					stream_string += "%-32g" % stream.id
				print(stream_string)
				print('-' * (8 + len(sorted_streams) * 32))
				if not levelrange:
					levelrange = [[0,len(levels)]]
				#pprint.pprint(levelrange)
				for levell,levelr in levelrange:
					if levelr == 0:
						continue
					for level in range(levell,levelr):
						line = "%-8g" % level
						for stream in sorted_streams:
							changeset = None
							try:
								changeset = stream.lastchangeset.get_ancestors(include_self=True).get(level=level)
							except ChangeSet.DoesNotExist:
								if level == stream.lastchangeset.level:
									changeset = streamlastchangeset
								else:
									line += " ".ljust(32)
							except ChangeSet.MultipleObjectsReturned:
								shouter.shout("\t !!! oops, multiple changeset in the same level")
								input("any key to continue or break")
							if changeset:
								if changeset.sequence > 1:
									line += (changeset.uuid + "(%g)" % changeset.sequence).ljust(32)
								else:
									line += changeset.uuid.ljust(32)
						print(line)
					print('.' * (8 + len(sorted_streams) * 32))
		except Exception as e:
			shouter.shout("\t!!!Something strange happed")
	elif options.inforeport:
		stream_rebuild_tree()
		try:
			stream0 = Stream.objects.get(name=optionsstream)
			list_streams = []
			if streams:
				for si in streams:
					if si != stream0.id:
						list_streams.append(Stream.objects.get(id=si))
			else:
				list_streams = list(Stream.objects.filter(component=component0).exclude(id=stream0.id))
		except Stream.DoesNotExist:
			shouter.shout("\t !!! some stream name or id you specified do not exist")
			sys.exit(9)
		try:
			filtered_streams = list(filter(lambda x: x.history_updated,list_streams))
			sorted_streams = sorted(filtered_streams, key = lambda s: s.lastchangeset.get_ancestors(include_self=True).count(), reverse = True)
			#sorted_streams = sorted(streams, key = lambda s: s.historys.count(), reverse = True)
			sorted_streams.insert(0,stream0)
			levels = list(set(stream0.firstchangeset.get_descendants().values_list('level',flat=True)))
			print("REPORTING")
			print("\tfor rtc:")
			print("\t\tTotal projectareas: %g" % ProjectArea.objects.count())
			print("\t\tTotal components: %g" % Component.objects.count())
			print("\t\tTotal streams: %g" % Stream.objects.count())
			print("\tfor component %s:" % component_name)
			print("\t\tTotal changesets: %g" % stream0.firstchangeset.get_descendant_count())
			print("\t\tTotal streams: %g" % Stream.objects.filter(component__name=component_name).count())
			print('-' * (8 + len(sorted_streams) * 8))
			print("stream_name".ljust(64) + "stream_id (range)\tadditional information")
			for stream in sorted_streams:
				stream_string = ''
				for streamparent in stream.get_ancestors().exclude(id=stream0.id):
					stream_string += "%g--" % streamparent.id
				stream_string = ("%s%s" % (stream_string, stream.name)).ljust(64)
				if stream.firstchangeset and stream.lastchangeset:
					stream_string += "%-5g(%5g-%-5g)" % (stream.id, stream.firstchangeset.level,stream.lastchangeset.level)
				elif stream.lastchangeset:
					stream_string += "%-5g(%5g-%-5g)" % (stream.id, stream.lastchangeset.get_ancestors().first().level,stream.lastchangeset.level)
				else:
					stream_string += "%-18g" % (stream.id)
				if options.withfirstbaselineinstream:
					if stream.baselineinstream_set.all():
						bis0 = stream.baselineinstream_set.all().order_by('baseline__bid')[0]
						if bis0.historys.all():
							stream_string += "%16g(%5g-%-g)" % (bis0.baseline.bid,bis0.historys.first().level, bis0.historys.last().level)
						else:
							stream_string += "%16g" % bis0.baseline.bid
				else:
					if stream.firstchangeset:
						stream_string += "\t%s" % stream.firstchangeset.uuid
				print(stream_string)
			print('-' * (8 + len(sorted_streams) * 8))
			if options.withchangesets:
				stream_string = 'chg\stm'.ljust(8)
				for stream in sorted_streams:
					stream_string += "%-8g" % stream.id
				print(stream_string)
				print('-' * (8 + len(sorted_streams) * 8))
				if not levelrange:
					if len(levels) < 600:
						levelrange = [[stream0.firstchangeset.level,stream0.firstchangeset.level + len(levels) + 1]]
					else:
						changeset_set = set()
						changeset_level_list = []
						for stream in sorted_streams:
							if not stream.firstchangeset:
								stream.determine_branching(stream0=stream0)
							changeset_set.add(stream.firstchangeset)
							changeset_set.add(stream.lastchangeset)
						changeset_level_list = list(map(lambda x: x.level, changeset_set))
						changeset_level_list.sort()
						#print("You may wish to use your own --levelrange to display report refer to %s" % json.dumps(changeset_level_list))
						levelrange = [[0,0]]
						l_prev = levelinterval
						for l in changeset_level_list:
							nrange = [l_prev - levelinterval, l_prev + levelinterval]
							if not nrange in levelrange:
								if nrange[1] <= levelrange[-1][1]:
									pass
								else:
									if nrange[0] <= levelrange[-1][1]:
										nrange[0] = levelrange[-1][1]
									levelrange.append(nrange)
							if l > l_prev + levelinterval:
								l_prev = l
							else:
								pass
						nrange = [l_prev - levelinterval, l_prev + levelinterval]
						if not nrange in levelrange:
							if nrange[1] <= levelrange[-1][1]:
								pass
							else:
								if nrange[0] <= levelrange[-1][1]:
									nrange[0] = levelrange[-1][1]
								levelrange.append(nrange)
				#pprint.pprint(levelrange)
				for levell,levelr in levelrange:
					if levelr == 0:
						continue
					for level in range(levell,levelr):
						line = "%-8g" % level
						for stream in sorted_streams:
							changeset = None
							try:
								changeset = stream.lastchangeset.get_ancestors().get(level=level)
							except ChangeSet.DoesNotExist:
								if level == stream.lastchangeset.level:
									changeset = stream.lastchangeset
								else:
									line += " ".ljust(8)
							except ChangeSet.MultipleObjectsReturned:
								shouter.shout("\t !!! oops, multiple changeset in the same level")
								input("any key to continue or break")
							if changeset:
								if changeset.sequence > 1:
									line += changeset.uuid[0:5] + "(%g)" % changeset.sequence
								else:
									line += changeset.uuid[0:5].ljust(8)
						print(line)
					print('.' * (8 + len(sorted_streams) * 8))
			if options.withbaselines:
				print('-' * (8 + len(sorted_streams) * 18))
				stream_string = 'bsl\stm'.ljust(8)
				for stream in sorted_streams:
					if stream.firstchangeset and stream.lastchangeset:
						stream_string += "%-5g(%5g-%-5g)" % (stream.id, stream.firstchangeset.level,stream.lastchangeset.level)
					elif stream.lastchangeset:
						stream_string += "%-5g(%5g-%-5g)" % (stream.id, stream.lastchangeset.get_ancestors().first().level,stream.lastchangeset.level)
					else:
						stream_string += "%-18g" % stream.id
				print(stream_string)
				print('-' * (8 + len(sorted_streams) * 18))
				levels_bis = []
				if streams:
					bis_set = set()
					for stream in sorted_streams:
						for bis in stream.baselineinstream_set.all():
							bis_set.add(bis)
					levels_bis = list(map(lambda x: x.baseline.level, bis_set))
				else:
					levels_bis = list(set(BaselineInStream.objects.filter(stream__component=component0).values_list('baseline__level',flat=True)))
				levels_bis = list(set(levels_bis))
				levels_bis.sort()
				for level in levels_bis:
					line = "%-8g" % level
					for stream in sorted_streams:
						try:
							bis = stream.baselineinstream_set.get(baseline__level=level)
							if bis.historys.all():
								line += "%-5g(%5g-%-5g)" % (bis.baseline.bid, bis.historys.first().level, bis.historys.last().level)
							else:
								line += "%-18g" % bis.baseline.bid
						except BaselineInStream.DoesNotExist:
							line += " ".ljust(18)
						except BaselineInStream.MultipleObjectsReturned:
							line += ("got %g" % stream.baselineinstream_set.filter(baseline__level=level).count()).ljust(18)
					print(line)
				print('-' * (8 + len(sorted_streams) * 18))
		except Stream.DoesNotExist:
			shouter.shout("\t!!! stream you specified does not exist")
		
	elif options.infoinit:
		if os.path.exists(os.path.join(settings.BASE_DIR,'rtc','fixtures','infoinit.json')):
			shouter.shout("\t .!. %s already exists, do you wish to overwrite it" % os.path.join(settings.BASE_DIR,'rtc','fixtures','infoinit.json'))
			answer = input("any key to continue or break")
		shouter.shout("updating information")
		ccs,creatd = Category.objects.get_or_create(name='changeset')
		cco,created = Category.objects.get_or_create(name='component')
		cst,created = Category.objects.get_or_create(name='stream')
		cbl,created = Category.objects.get_or_create(name='baseline')
		sync_project()
		sync_streams()
		print("REPORTING")
		print("\tfor rtc:")
		print("\t\tTotal projectareas: %g" % ProjectArea.objects.count())
		print("\t\tTotal components: %g" % Component.objects.count())
		print("\t\tTotal streams: %g" % Stream.objects.count())
		#shouter.shout("update snapshots for stream")
		if not os.path.exists(os.path.join(settings.BASE_DIR,'rtc','fixtures','infoinit.json')):
			shouter.shout("\t...Now backup this initialization to save time for the future")
			print(subprocess.check_output("mkdir -p %s; %s dumpdata rtc > %s; exit 0"  % (os.path.join(settings.BASE_DIR,'rtc/fixtures'),os.path.join(settings.BASE_DIR,'manage.py'),os.path.join(settings.BASE_DIR,'rtc/fixtures/infoinit.json')),shell=True).decode())
			shouter.shout("Backed up rtc initializations")
		else:
			shouter.shout("\t...fixture %s already exists, if you wish to overwrite it, delete it first" % os.path.join(settings.BASE_DIR,'rtc','fixtures','infoinit.json'))

	elif options.infoupdate:
		shouter.shout("updating information")
		if ChangeSet.objects.root_nodes().count() > 1:
			shouter.shout("\t!!! got two changeset trees, you got some issue from previous stream process, correct it first please")
			shouter.shout("\t... you should be able to find intermediate results at tmp/%s" % component_name)
			sys.exit(9)
		if options.branchfurther:
			shell.execute("touch /tmp/.stream_rebuild; exit 0")
			if options.streamparent:
				try:
					streamparent = Stream.objects.get(name=options.streamparent)
				except Stream.DoesNotExist:
					try:
						streamparent = Stream.objects.get(int(options.streamparent))
					except Exception as e:
						shouter.shout("\t!!! you have to specify the parent branch to fine determine branching points with its name or id")
						sys.exit(9)
				except Exception as e:
					shouter.shout("\t!!! you have to specify the parent branch to fine determine branching points with its name or id")
					sys.exit(9)
			else:
				shouter.shout("\t!!! you have to specify the parent branch to fine determine branching points with its name or id")
				sys.exit(9)
			shouter.shout("\t... try to further determine branching points, using your specified parent stream %s" % streamparent.name)
			changesetparent = streamparent.firstchangeset
			if changesetparent:
				stream_ids = list(changesetparent.firstchangesets.all().exclude(id=streamparent.id).filter(level=streamparent.level).values_list('id',flat=True))
				for stream_id in stream_ids:
					stream = Stream.objects.get(id=stream_id)
					shouter.shout("\t... determining branching point using %s as parent for %s" % (streamparent.name, stream.name))
					if options.sleepinterval:
						time.sleep(int(options.sleepinterval))
					else:
						time.sleep(1)
					stream.determine_branching(stream0=streamparent)
				for stream_id in stream_ids:
					while True:
						stream = Stream.objects.get(id=stream_id)
						shouter.shout("\t... verifying branching determine for stream %s" % stream.name )
						if stream.parent != streamparent:
							shouter.shout("\t.!.determining branching not complete for stream %s" % stream.name)
							input("\t... rebuild tree?")
							Stream.objects.rebuild()
						elif stream.level != streamparent.level + 1:
							shouter.shout("\t.!.determining branching not complete for stream %s" % stream.name)
							input("\t... rebuild tree?")
							Stream.objects.rebuild()
						else:
							break
			else:
				shouter.shout("\t!!!the parent stream should have its firstchangeset attribute")
			sys.exit(9)
		sync_streams(component_name=component_name,short_cut=True)
		shouter.shout("\t... refresh all of the baselines for component %s" % component0.name)
		component0.update_baselines()
		try:
			stream0 = Stream.objects.get(name=optionsstream)
			list_streams = []
			if streams:
				for si in streams:
					if si != stream0.id:
						list_streams.append(Stream.objects.get(id=si))
			else:
				list_streams = list(Stream.objects.filter(component=component0).exclude(id=stream0.id))
		except Stream.DoesNotExist:
			shouter.shout("\t !!! some stream name or id you specified do not exist")
			sys.exit(9)
		#shouter.shout("update snapshots for stream")
		#input("backup now")
		component0.update_baselines()
		if options.incremental:
			shouter.shout("\t... processing stream %s" % stream0.name)
			stream0.update_baselines(post_incremental=True)
			stream0.update_history(post_incremental=True)
			stream0.update_baselines_changesets(post_incremental=True)
			for stream in list_streams:
				shouter.shout("\t... processing stream %s" % stream.name)
				stream.update_baselines(post_incremental=True)
				stream.update_history(post_incremental=True)
				stream.update_baselines_changesets(post_incremental=True)
			sys.exit(9)
		 
		#shouter.shout("\tsnapshots for stream %s" % stream0.name)
		if not stream0.history_updated or not stream0.changesets_compared:
			print("\t... processing stream %s" % stream0.name)
			shouter.shout("\tbaselines for stream %s" % stream0.name)
			stream0.update_baselines()
	#		stream0.update_snapshots()
	#	for snapshot in stream0.snapshots.all():
	#		shouter.shout("\t...%s %s" % (snapshot.name, snapshot.comment))
	#		snapshot.update_baselines()
			if not stream0.history_updated:
				stream0.update_history(initial=True)
				stream0 = Stream.objects.get(id=stream0.id)
				stream0.determine_branching()
				stream0 = Stream.objects.get(id=stream0.id)
			if not stream0.changesets_compared:
				if not options.shortcut_analyze:
					stream0.update_baselines_changesets()
			if db['ENGINE'] == 'django.db.backends.sqlite3':
				subprocess.check_output("sync; sleep 1; sync; sleep 1; cp -f %s %s ; exit 0 " % (db['NAME'], os.path.join(settings.BASE_DIR,'tmp',component_name,'db.' + re.sub(r' ','',stream0.name))),shell=True)
			elif db['ENGINE'] == 'django.db.backends.mysql':
				if db['PASSWORD']:
					subprocess.check_output("mysqldump -h%s -u%s -p\"%s\" -c %s > %s; exit 0" % (db['HOST'], db['USER'], db['PASSWORD'], db['NAME'], os.path.join(settings.BASE_DIR,'tmp',component_name,'sql.' + re.sub(r' ','',stream0.name))),shell=True)
				else:
					subprocess.check_output("mysqldump -h%s -u%s -c %s > %s; exit 0" % (db['HOST'], db['USER'], db['NAME'], os.path.join(settings.BASE_DIR,'tmp',component_name,'sql.' + re.sub(r' ','',stream0.name))),shell=True)
			else:
				shouter.shout("\t.!. did not know how to backup your database, please do it manually")
				input("any key to continue or break")
			if not options.shortcut_analyze:
				if stream0.lastchangeset.get_ancestors(include_self=True).filter(compared=False).count() > 1:
					shouter.shout("\t.!. There are more than one changesets that were not compared, try to solve it with --incremental")
					stream0.update_baselines(post_incremental=True)
					stream0.update_history(post_incremental=True)
					stream0.update_baselines_changesets(post_incremental=True)
				if stream0.lastchangeset.get_ancestors(include_self=True).filter(compared=False).count() > 1:
					shouter.shout("\t.!. There are more than one changesets that were not compared, should you solve it with --infoupdate --incremental")
					input("continue or break")

		for stream in list_streams:
			if stream.history_updated and stream.changesets_compared:
				shouter.shout("%s has been processed" % stream.name)
				continue
			print("\t... processing stream %s" % stream.name)
	#		shouter.shout("\tsnapshots for stream %s" % stream.name)
			shouter.shout("\tbaselines for stream %s" % stream.name)
			stream.update_baselines()
	#			stream.update_snapshots()
	#		for snapshot in stream.snapshots.all():
	#			shouter.shout("\t...%s %s" % (snapshot.name, snapshot.comment))
	#			snapshot.update_baselines()
			if not stream.history_updated:
				stream.update_history()
				stream = Stream.objects.get(id=stream.id)
				stream.determine_branching(stream0=stream0)
				stream = Stream.objects.get(id=stream.id)
			if not stream.history_updated or stream.history_partial:
				input("\t !!! got issue updating history, continue or break?")
			if not stream.changesets_compared:
				if not options.shortcut_analyze:
					stream.update_baselines_changesets()
			if db['ENGINE'] == 'django.db.backends.sqlite3':
				subprocess.check_output("sync; sleep 1; sync; sleep 1; cp -f %s %s ; exit 0 " % (db['NAME'], os.path.join(settings.BASE_DIR,'tmp',component_name,'db.' + re.sub(r' ','',stream.name))),shell=True)
			elif db['ENGINE'] == 'django.db.backends.mysql':
				if db['PASSWORD']:
					subprocess.check_output("mysqldump -h%s -u%s -p\"%s\" -c %s > %s; exit 0" % (db['HOST'], db['USER'], db['PASSWORD'], db['NAME'], os.path.join(settings.BASE_DIR,'tmp',component_name,'sql.' + re.sub(r' ','',stream.name))),shell=True)
				else:
					subprocess.check_output("mysqldump -h%s -u%s -c %s > %s; exit 0" % (db['HOST'], db['USER'], db['NAME'], os.path.join(settings.BASE_DIR,'tmp',component_name,'sql.' + re.sub(r' ','',stream.name))),shell=True)
			else:
				shouter.shout("\t.!. did not know how to backup your database, please do it manually")
				input("any key to continue or break")
			if not options.shortcut_analyze:
				if stream.lastchangeset.get_ancestors(include_self=True).filter(compared=False).count() > 1:
					shouter.shout("\t.!. There are more than one changesets that were not compared, try to solve it with --infoupdate --incremental")
					stream.update_baselines(post_incremental=True)
					stream.update_history(post_incremental=True)
					stream.update_baselines_changesets(post_incremental=True)
				if stream.lastchangeset.get_ancestors(include_self=True).filter(compared=False).count() > 1:
					shouter.shout("\t.!. There are more than one changesets that were not compared, should you solve it with --infoupdate --incremental")
					input("continue or break")
#		shouter.shout("determine last changeset of baselines for compoent %s" % component_name)
#		for baseline in Baseline.objects.filter(component=component0): 
#			shouter.shout("processing baseline %s" % baseline.name)
#			baseline.update_lastchangeset()
		shouter.shout("important streams are")
#		for stream in Stream.objects.filter(name__iregex=r'.*mainline|.*trunk|.*prs'):
#		for stream in Stream.objects.filter(name=optionsstream):
		for stream in Stream.objects.filter(component__name=component_name):
			print("\t\t%s" % str(stream))

	elif options.migrate:
		shouter.shout("\t... trying to backup the database before migration happen if not yet")
		if db['ENGINE'] == 'django.db.backends.sqlite3':
			if os.path.exists(db['NAME']):
				if not os.path.exists("%s.before.migrate" % db['NAME']):
					shell.execute("cp -f %s %s.before.migrate ; exit 0 " % (db['NAME'], db['NAME']))
		elif db['ENGINE'] == 'django.db.backends.mysql':
			if db['PASSWORD']:
				shell.exetue("mysqldump -h%s -u%s -p\"%s\" -c %s > %s; exit 0" % (db['HOST'], db['USER'], db['PASSWORD'], db['NAME'], os.path.join(settings.BASE_DIR,'sql.' + db['NAME'] + '.before.migrate')))
			else:
				shell.execute("mysqldump -h%s -u%s -c %s > %s; exit 0" % (db['HOST'], db['USER'], db['NAME'], os.path.join(settings.BASE_DIR,'sql.' + db['NAME'] + '.before.migrate')))
		else:
			shouter.shout("\t.!. did not know how to backup your database, please do it manually")
			input("any key to continue or break")
		if options.withrelogin:
			rtclogin_restart()
		def migrate_stream0(post_incremental=False):
			stream = Stream.objects.get(id=stream0.id)
			stream.refresh_from_db()
			rtcdir = os.path.join(RTCDIR,re.sub(r' ','',stream.name))
			workspace_stream = 'git_migrate_%s_%s' % (stream.component.name, re.sub(r' ','', stream.name))
			ws_migrate,created = Workspace.objects.get_or_create(name=workspace_stream)
			flag_do_migrate = False
			if not post_incremental:
				if stream_based and not stream.migrated:
					flag_do_migrate = True
					if created:
						shouter.shout("\t... starting the brand new migration for trunk stream %s" % stream.name)
						if ws_migrate.ws_exist():
							ws_migrate.ws_delete()
						ws_migrate.uuid = ''
						ws_migrate.snapshot = None
						ws_migrate.save()
						ws_migrate.ws_create()
						ws_migrate.ws_update()
						ws_migrate.ws_list()
						ws_migrate.stream = stream
						ws_migrate.component = stream.component
						ws_migrate.save()
						ws_migrate.ws_add_component()
						ws_migrate.ws_set_flowtarget()
						rtc_initialize(rtcdir, gitdir=gitdir,workspace=ws_migrate,component=component0,load=True,is_master=True)
				else:
					shouter.shout("\t...stream %s has been migrated to git branch %s" % (stream.name,stream.name))
			elif stream.migrated:
				shouter.shout("\t... starting to pickup the changesets that recently commited")
				flag_do_migrate = True
			else:
				shouter.shout("\t... base stream not migrated yet, terminating")
				sys.exit(9)
			if flag_do_migrate:
				shouter.shout("\t... trying to continue the existing migration for trunk stream %s" % stream.name)
				os.chdir(rtcdir)
				shell.execute("git -C %s pull" % rtcdir)
				changesets_migrated = stream.lastchangeset.get_ancestors(include_self=True).filter(migrated=True)
				last_migrated_changeset = changesets_migrated.last()
				commitid = git_last_commitid(rtcdir=rtcdir)
				if stream.lastchangeset.commit and commitid == stream.lastchangeset.commit.commitid:
					shouter.shout("\t... already migrated to the end, mark migrated if not yet")
					if not stream.migrated:
						stream.migrated = True
						stream.save()
				elif last_migrated_changeset.commit.commitid != commitid:
					shouter.shout("\t!!! got issue resuming the migration: last migrated changeset does not corresponds to the last commitid")
					sys.exit(9)
				else:
					shouter.shout("\t.!. what happend to stream.lastchangeset.commit")
				items = rtc_show_history(workspace=ws_migrate,component=ws_migrate.component,maxitems=2)
				if not 'changes' in items.keys() or len(items['changes']) != 2:
					if len(items['changes']) == 1 and items['changes'][0]['uuid'] == last_migrated_changeset.uuid:
						shouter.shout("\t... got only 1 changeset, good for streambase")
					else:
						shouter.shout("\t!!! got incorrect resuming (history error), inspect it manually please")
						sys.exit(9)
				else:
					if items['changes'][0]['uuid'] != last_migrated_changeset.uuid:
						if ChangeSet.objects.filter(uuid=items['changes'][0]['uuid']):
							shouter.shout("\t!!! got incorrect resuming (first history not last migrated), inspect it manually please")
							sys.exit(9)
						elif items['changes'][1]['uuid'] == last_migrated_changeset.uuid:
							shouter.shout("\t... aside from the merge, 2nd history item is the last migrated")
							shouter.shout("\t.!. you have a conflict merge in your workspace already, pay attention")
						else:
							shouter.shout("\t!!! got incorrect resuming (rest situations), inspect it manually please")
							sys.exit(9)
				#if not ws_migrate.stream.migrated:
				queryset_not_migrated = ws_migrate.stream.lastchangeset.get_ancestors(include_self=True).filter(migrated=False)
				stream.refresh_from_db()
				if queryset_not_migrated:
					if queryset_not_migrated.first().parent != last_migrated_changeset:
						shouter.shout("\t!!! got incorrect resuming, inspect it manually please")
						sys.exit(9)
					else:
						ws_migrate.ws_suspend()
						ws_migrate.ws_resume(use_accept=True,do_validation=True)
				else:
					shouter.shout("\t... stream %s has been migrated already" % stream.name)
					if not stream.migrated:
						stream.migrated = True
						stream.save()
				stream.refresh_from_db()
				stream.post_migrate_actions(rtcdir=rtcdir,post_incremental=post_incremental)

		def migrate_stream(stream,post_incremental=False,do_validation=False):
			stream.refresh_from_db()
			rtcdir = os.path.join(RTCDIR,re.sub(r' ','',stream.name))
			workspace_stream = 'git_migrate_%s_%s' % (stream.component.name, re.sub(r' ','', stream.name))
			if not stream.validated:
				validated = stream.validate_branchingpoint()
				stream.refresh_from_db()
			if not stream.validated:
				shouter.shout("\t!!! can not migration stream %s since it is not validated" % stream.name)
				sys.exit(9)
			ws_migrate,created = Workspace.objects.get_or_create(name=workspace_stream)
			flag_do_migrate = False

			if not post_incremental:
				if stream_based and not stream.migrated:
					flag_do_migrate = True
					if stream.lastchangeset == stream.firstchangeset and stream.firstchangeset.migrated:
						shouter.shout("\t ... congratulations, stream %s does not contain any unmigrated changesets, done here" % stream.name)
						stream.migrated = True
						stream.save()
						return ""
					if created:
						shouter.shout("\t... starting the brand new migration for non-trunk stream %s" % stream.name)
						shouter.shout("\t!!! should not come here, stream.validate_branchingpoint() should've done this")
						sys.exit(9)
				else:
					shouter.shout("\t...non-trunk stream %s is migrated already" % stream.name)
			elif stream.migrated:
				shouter.shout("\t... starting to pickup the changesets that recently commited")
				flag_do_migrate = True
			else:
				shouter.shout("\t... stream not migrated yet, bypass incremental")
				return
			if flag_do_migrate:
				if not ws_migrate.stream:
					ws_migrate.stream = stream
					ws_migrate.save()
				if not ws_migrate.component:
					ws_migrate.component = stream.component
					ws_migrate.save()
				shouter.shout("\t... accepting all changeset up to branching point")
				shouter.shout("\t... trying to continue the existing migration for non-trunk stream %s" % stream.name)
				os.chdir(rtcdir)
				shell.execute("git -C %s pull" % rtcdir)
				changesets_migrated = stream.lastchangeset.get_ancestors(include_self=True).filter(migrated=True)
				last_migrated_changeset = changesets_migrated.last()
				commitid = git_last_commitid(rtcdir=rtcdir)
				if stream.lastchangeset.commit and commitid == stream.lastchangeset.commit.commitid:
					shouter.shout("\t... already migrated to the end, mark migrated if not yet")
					if not stream.migrated:
						stream.migrated = True
						stream.save()
				elif last_migrated_changeset.commit.commitid != commitid:
					shouter.shout("\t!!! got issue resuming the migration: last migrated changeset does not corresponds to the last commitid")
					sys.exit(9)
				items = rtc_show_history(workspace=ws_migrate,component=ws_migrate.component,maxitems=2)
				if not 'changes' in items.keys() or len(items['changes']) != 2:
					shouter.shout("\t!!! got incorrect resuming, inspect it manually please")
					sys.exit(9)
				else:
					if items['changes'][0]['uuid'] != last_migrated_changeset.uuid:
						if ChangeSet.objects.filter(uuid=items['changes'][0]['uuid']):
							shouter.shout("\t!!! got incorrect resuming (first history not last migrated), inspect it manually please")
							sys.exit(9)
						elif items['changes'][1]['uuid'] == last_migrated_changeset.uuid:
							shouter.shout("\t... aside from the merge, 2nd history item is the last migrated")
							shouter.shout("\t.!. you have a conflict merge in your workspace already, pay attention")
						else:
							shouter.shout("\t!!! got incorrect resuming (rest situations), inspect it manually please")
							sys.exit(9)
				#if not ws_migrate.stream.migrated:
				queryset_not_migrated = ws_migrate.stream.lastchangeset.get_ancestors(include_self=True).filter(migrated=False)
				stream.refresh_from_db()
				if queryset_not_migrated:
					if queryset_not_migrated.first().parent != last_migrated_changeset:
						shouter.shout("\t!!! got incorrect resuming, inspect it manually please")
						sys.exit(9)
					else:
						ws_migrate.ws_resume(use_accept=True,do_validation=do_validation)
				else:
					shouter.shout("\t... stream %s has been migrated already" % stream.name)
					if not stream.migrated:
						stream.migrated = True
						stream.save()
				stream.refresh_from_db()
				stream.post_migrate_actions(rtcdir=rtcdir,post_incremental=post_incremental)


		def migrate_tagbaselines():
			gitdir = os.path.join(migration_top,component0.name,'gitdir')
			rtcdir = os.path.join(RTCDIR,"taggings")
			if not os.path.exists(rtcdir):
				shouter.shout("\t... clone git repository %s to %s" % (gitdir, rtcdir))
				shell.execute("git clone -b %s %s %s; sync" % (re.sub(r' ','',stream0.name), gitdir, rtcdir))
			else:
				shouter.shout("\t... pull git changes")
				shell.execute("git -C %s pull; sync" % rtcdir)
			baselines_to_tag = []
			for s in Stream.objects.filter(migrated=True):
				for bis in s.baselineinstream_set.filter(verified=True):
					baseline = bis.baseline
					if not baseline.tagged:
						if not baseline.lastchangeset:
							baseline.lastchangeset = bis.lastchangeset
							baseline.save()
						elif baseline.lastchangeset != bis.lastchangeset:
							shouter.shout("got in-consistent baseline %s, manual verify please" % baseline.name)
							sys.exit(9)
						else:
							pass
						'''if not baseline.tagname:
							if baseline.name:
								bname = re.sub(r':','_',re.sub(r' ','',baseline.name))
								if not Baseline.objects.filter(tagname=bname):
									baseline.tagname = bname
								else:
									baseline.tagname = "%s_%g" % (bname, baseline.lastchangeset.level)
							elif baseline.comment:
								bcomment = re.sub(r':','_',re.sub(r' ','',baseline.comment))
								if not Baseline.objects.filter(tagname=bcomment):
									baseline.tagname = bcomment
								else:
									baseline.tagname = "%s_%g" % (bcomment, baseline.lastchangeset.level)
							else:
								baseline.tagname = "baseline_at_level_%g" % baseline.lastchangeset.level
							baseline.save()
						baselines_to_tag.append(baseline) '''
						# shen hack tagging, tag BLs without Daily_
						if not baseline.tagname:
							if baseline.name:
								bname = re.sub(r':','_',re.sub(r' ','',baseline.name))
								if (not Baseline.objects.filter(tagname=bname)) and ('Daily_' not in bname):
									baseline.tagname = bname
									baseline.save()
									baselines_to_tag.append(baseline)
			for baseline in list(set(baselines_to_tag)):
				print(baseline.tagname)
				if baseline.lastchangeset.commit:
					print(shell.getoutput("git -C %s tag %s %s" % (rtcdir, baseline.tagname, baseline.lastchangeset.commit.commitid),clean=False))
					baseline.tagged = True
					baseline.save()
			#pprint.pprint(baselines_to_tag)
			shell.execute("git -C %s push --tags; sync" % rtcdir)

		if not os.path.exists(gitdir):
			git_initialize(gitdir)

		if options.tagbaselines:
			migrate_tagbaselines()
			sys.exit(0)

		migrate_stream0(post_incremental=options.incremental)
		do_validation = False
		if options.withvalidation:
			do_validation = True
		if options.streams:
			for stream in list_streams:
				stream.refresh_from_db()
				if stream.parent:
					if stream.parent.migrated:
						shouter.shout("\t...... start to migrate the stream %s" % stream.name)
						migrate_stream(stream,post_incremental=options.incremental,do_validation=do_validation)
					else:
						shouter.shout("\t...... start to migrate the parent stream %s first" % stream.parent.name)
						if stream.parent == stream0:
							shouter.shout("\t!!! migrate the trunk stream first with --migrate only")
							sys.exit(9)
						migrate_stream(stream.parent,do_valiation=do_validation)
						stream = Stream.objects.get(id=stream.id)
						stream.refresh_from_db()
						if stream.parent.migrated:
							shouter.shout("\t...... start to migrate the stream %s" % stream.name)
							migrate_stream(stream,post_incremental=options.incremental,do_validation=do_validation)
						else:
							shouter.shout("\t!!! parent stream is not migrated yet")
							sys.exit(9)
				else:
					shouter.shout("\t!!! strange, stream should have an parent stream that it branched from")
					sys.exit(9)
		elif options.allstreams:
			if options.incremental:
				list_streams = list(filter(lambda x: x.migrated and x.lastchangeset and x.firstchangeset and x.lastchangeset.get_ancestors(include_self=True).filter(level__gt=x.firstchangeset.level).filter(migrated=False), Stream.objects.all()))
				sorted_streams = sorted(list_streams, key = lambda x: x.level)
				for stream in sorted_streams:
					shouter.shout("\t... handling %s" % stream.name)
					if stream.migrated:
						shouter.shout("\t...... stream %s has been migrated, doing incremental now" % stream.name)
						if stream.parent:
							if stream.parent.migrated:
								shouter.shout("\t...... start to migrate the stream %s" % stream.name)
								migrate_stream(stream,post_incremental=options.incremental,do_validation=do_validation)
							else:
								shouter.shout("\t...... start to migrate the parent stream %s first" % stream.parent.name)
								if stream.parent == stream0:
									shouter.shout("\t!!! migrate the trunk stream first with --migrate only")
									sys.exit(9)
								migrate_stream(stream.parent,do_validation=do_validation)
								stream = Stream.objects.get(id=stream.id)
								stream.refresh_from_db()
								if stream.parent.migrated:
									shouter.shout("\t...... start to migrate the stream %s" % stream.name)
									migrate_stream(stream,post_incremental=options.incremental,do_validation=do_validation)
								else:
									shouter.shout("\t!!! parent stream is not migrated yet")
									sys.exit(9)
						else:
							shouter.shout("\t!!! strange, stream should have an parent stream that it branched from")
							sys.exit(9)
					else:
						shouter.shout("\t!!! stream not migrated yet, can not do incremental")
						sys.exit(9)
			else:
				for stream in Stream.objects.filter(component=component0).exclude(id=stream0.id):
					shouter.shout("\t... handling %s" % stream.name)
					if stream.migrated:
						shouter.shout("\t...... stream %s has been migrated already" % stream.name)
					else:
						if stream.parent:
							if stream.parent.migrated:
								shouter.shout("\t...... start to migrate the stream %s" % stream.name)
								migrate_stream(stream,post_incremental=options.incremental,do_validation=do_validation)
							else:
								shouter.shout("\t...... start to migrate the parent stream %s first" % stream.parent.name)
								if stream.parent == stream0:
									shouter.shout("\t!!! migrate the trunk stream first with --migrate only")
									sys.exit(9)
								migrate_stream(stream.parent,do_validation=do_validation)
								stream = Stream.objects.get(id=stream.id)
								stream.refresh_from_db()
								if stream.parent.migrated:
									shouter.shout("\t...... start to migrate the stream %s" % stream.name)
									migrate_stream(stream,post_incremental=options.incremental,do_validation=do_validation)
								else:
									shouter.shout("\t!!! parent stream is not migrated yet")
									sys.exit(9)
						else:
							shouter.shout("\t!!! strange, stream should have an parent stream that it branched from")
							sys.exit(9)
		else:
			if options.incremental:
				list_streams = list(filter(lambda x: x.migrated and x.lastchangeset and x.firstchangeset and x.lastchangeset.get_ancestors(include_self=True).filter(level__gt=x.firstchangeset.level).filter(migrated=False), Stream.objects.all()))
				sorted_streams = sorted(list_streams, key = lambda x: x.level)
				for stream in sorted_streams:
					shouter.shout("\t... handling %s" % stream.name)
					if stream.migrated:
						shouter.shout("\t...... stream %s has been migrated, doing incremental now" % stream.name)
						if stream.parent:
							if stream.parent.migrated:
								shouter.shout("\t...... start to migrate the stream %s" % stream.name)
								migrate_stream(stream,post_incremental=options.incremental,do_validation=do_validation)
							else:
								shouter.shout("\t...... start to migrate the parent stream %s first" % stream.parent.name)
								if stream.parent == stream0:
									shouter.shout("\t!!! migrate the trunk stream first with --migrate only")
									sys.exit(9)
								migrate_stream(stream.parent,do_validation=do_validation)
								stream = Stream.objects.get(id=stream.id)
								stream.refresh_from_db()
								if stream.parent.migrated:
									shouter.shout("\t...... start to migrate the stream %s" % stream.name)
									migrate_stream(stream,post_incremental=options.incremental,do_validation=do_validation)
								else:
									shouter.shout("\t!!! parent stream is not migrated yet")
									sys.exit(9)
						else:
							shouter.shout("\t!!! strange, stream should have an parent stream that it branched from")
							sys.exit(9)
					else:
						shouter.shout("\t!!! stream not migrated yet, can not do incremental")
						sys.exit(9)
			else:
				shouter.shout("\t.!. please use --migrate --streams [ stream_id1, stream_id2, ...] to do the migration for non-trunk streams")
				shouter.shout("\t.!. or use --migrate --allstream to migrate all rest streams, you may need to run it multiple times for complicated branches")
		
	else:
#		sys.argv.insert(1,cmd)
		from django.core.management import execute_from_command_line
		execute_from_command_line(sys.argv)



