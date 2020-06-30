from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from rtc.models import Component, Stream, ChangeSet, Baseline, BaselineInStream, Snapshot
import subprocess
import time
from django.conf import settings

# @login_required
def homepage(request):
	return render(request, "homepage.html", {settings: settings})
