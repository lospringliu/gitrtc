from django.contrib import admin

# Register your models here.
from  mptt.admin import MPTTModelAdmin
from rtc.models import *

class JsonRecordAdmin(admin.ModelAdmin):
	list_display = ('command','timestamp')
	list_per_page =  100
	save_on_top = True

class ChangeSetAdmin(MPTTModelAdmin):
	list_display = ('uuid','comment','migrated')
	list_per_page = 100

class GitCommitAdmin(admin.ModelAdmin):
	list_display = ('commitid','timestamp')
	list_per_page = 100

class StreamAdmin(admin.ModelAdmin):
	list_display = ('uuid','name')
	list_per_page = 100

class SnapshotAdmin(admin.ModelAdmin):
	list_display = ('uuid','migrated','name')
	list_per_page = 100
	list_filter=('stream',)

class BaselineAdmin(admin.ModelAdmin):
	list_display = ('uuid','name')
	list_per_page = 100
	list_filter = ('snapshot',)

admin.site.register(JsonRecord,JsonRecordAdmin)
admin.site.register(ChangeSet,ChangeSetAdmin)
admin.site.register(GitCommit,GitCommitAdmin)
admin.site.register(Stream,StreamAdmin)
admin.site.register(Baseline,BaselineAdmin)
admin.site.register(Snapshot,SnapshotAdmin)
