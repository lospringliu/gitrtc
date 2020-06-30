from django.contrib import admin

# Register your models here.
from  mptt.admin import MPTTModelAdmin
from rtc.models import *

class JsonRecordAdmin(admin.ModelAdmin):
	list_display = ('command','timestamp')
	list_per_page =  100

class ChangeSetAdmin(MPTTModelAdmin):
	list_display = ('uuid','comment','migrated')
	list_per_page = 100
	search_fields = ('uuid','comment')

class GitCommitAdmin(admin.ModelAdmin):
	list_display = ('commitid','timestamp')
	list_per_page = 100
	search_fields = ('commitid',)

class StreamAdmin(admin.ModelAdmin):
	list_display = ('uuid','name')
	list_per_page = 100
	search_fields = ('uuid','name',)

class SnapshotAdmin(admin.ModelAdmin):
	list_display = ('uuid','migrated','name')
	list_per_page = 100
	list_filter=('stream',)
	search_fields = ('name',)

class BaselineAdmin(admin.ModelAdmin):
	list_display = ('uuid','name')
	list_per_page = 100
	list_filter = ('snapshot',)
	search_fields = ('name',)

class WorkspaceAdmin(admin.ModelAdmin):
	list_display = ('name', 'component', 'stream')
	list_per_page = 300
	search_fields = ('name','component__name','stream__name')

admin.site.register(JsonRecord,JsonRecordAdmin)
admin.site.register(ChangeSet,ChangeSetAdmin)
admin.site.register(GitCommit,GitCommitAdmin)
admin.site.register(Stream,StreamAdmin)
admin.site.register(Baseline,BaselineAdmin)
admin.site.register(Snapshot,SnapshotAdmin)
admin.site.register(Workspace,WorkspaceAdmin)
admin.site.register(ProjectArea)
admin.site.register(GitBranch)
