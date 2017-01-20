import sys
import subprocess
from subprocess import call
from subprocess import check_output
import time
import re

import shouter

logcommands = False
encoding = None

def execute(command, outputfile=None, openmode="w"):
    shout_command_to_log(command, outputfile)
    if not outputfile:
        return call(command, shell=True)
    else:
        with open(outputfile, openmode, encoding=encoding) as file:
            return call(command, stdout=file, shell=True)


def getoutput(command,clean=True):
    shout_command_to_log(command)
    outputasbytestring = check_output(command, shell=True)
    output = outputasbytestring.decode(sys.stdout.encoding)
    if not clean:
        return output
    output = output.splitlines()
    strippedlines = []
    for line in output:
        cleanedline = line.strip()
        if cleanedline:
            strippedlines.append(cleanedline)
    return strippedlines


def quote(stringtoquote):
    stringtoquote = stringtoquote.strip()
    stringtoquote = re.sub(r'\\$','',stringtoquote)
    stringtoquote = stringtoquote.replace('\"', "'")  # replace " with '
    stringtoquote = stringtoquote.replace('`', "\`")  # replace " with '
    stringtoquote = stringtoquote.replace('\n', "\\n")  # replace newline 
    quotedstring = '\"' + stringtoquote + '\"'
    return escapeShellVariableExpansion(quotedstring)

def quote_old(stringtoquote):
    stringtoquote = stringtoquote.replace('\"', "'")  # replace " with '
    stringtoquote = stringtoquote.replace('`', "\`")  # replace " with '
    quotedstring = '\"' + stringtoquote + '\"'
    return escapeShellVariableExpansion(quotedstring)

def escapeShellVariableExpansion(comment):
    return comment.replace('$', '\\$')

def shout_command_to_log(command, outputfile=None):
    if logcommands:
        logmessage = "Executed Command: " + quote(command)
        if outputfile:
            shouter.shout(logmessage + " --> " + outputfile)
        else:
            shouter.shout(logmessage)


def setencoding(encodingtobeset):
    global encoding
    if encodingtobeset:
        encoding = encodingtobeset
