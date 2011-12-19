#!/usr/bin/env python

import sys
import os
import socket # for socket.gethostname()
import re
import subprocess
import time
import smtplib
try:
    from email.mime.text import MIMEText
except ImportError:
    # Old versions of python don't use the new module names
    from email.MIMEText import MIMEText


class Handler(object):
    """check for and handle an issue.  The default handler expects
    a regex pattern with at least the following groups:
        'hostname': hostname of the puppet slave
        'p_master': puppet master name of the puppet master"""

    subject = "unknown error on %(hostname)s"
    body = "There was an error on %(hostname)s"
    pattern = None

    def __init__(self, to, sender):
        object.__init__(self)
        self.to = to
        self.sender = sender

    def check(self, line):
        m = self.pattern.match(line)
        if m:
            self.handle(line, m.groupdict())

    def handle(self, line, match_dict):
        email("[puppet-monitoring][%(p_master)s] " % match_dict + self.subject % match_dict,
              self.body % match_dict + "\nRAW LOG:\n%s" % line, self.to, self.sender)

class InvalidCertHandler(Handler):
    subject = "%(hostname)s has an invalid certificate"
    body  = "The puppet slave %(hostname)s has an invalid puppet master certificate." + \
            "An attempt to clean it has been made, but no follow up has been done"
    pattern = re.compile('(?P<datetime>\w*\W*\d* \d*:\d*:\d*) (?P<p_master>[\w.\-_]*) puppetmasterd\[\d*\]: Certificate request does not match existing certificate; run \'(?P<suggestion>puppetca --clean (?P<hostname>[\w\d\-._]*))\'.')
    suggestion_parse = re.compile('puppetca --clean (?P<hostname>[\w\d\-._]*)')

    def __init__(self, to, sender):
        Handler.__init__(self, to, sender)

    def handle(self, line, match_dict):
        nodename = self.suggestion_parse.match(match_dict['suggestion']).group("hostname")
        rc = subprocess.call(['puppetca', '--clean', nodename])
        print "Cleaning puppetca on %s had rc of %d" % (nodename, rc)
        # TODO figure out a way to send rc
        Handler.handle(self, line, match_dict)

class WaitingCertHandler(Handler):
    subject = "%(hostname)s is waiting to be signed"
    body = "%(hostname)s is waiting to be signed.  It will probably be signed by " + \
           "accept-hostname-keys.sh"
    pattern = re.compile('(?P<datetime>\w*\W*\d* \d*:\d*:\d*) (?P<p_master>[\w.\-_]*) puppetmasterd\[\d*\]: Host (?P<hostname>[\w\d\-_.]*) has a waiting certificate request')

    def __init__(self, to, sender):
        Handler.__init__(self, to, sender)


class UnknownSlaveHandler(Handler):
    subject = "%(hostname)s is unknown to %(p_master)s"
    body = "%(hostname)s is not known to %(p_master)s but is trying to sync with it."
    pattern = re.compile("(?P<datetime>\w*\W*\d* \d*:\d*:\d*) (?P<p_master>[\w.\-_]*) puppetmasterd\[\d*\]: Could not find default node or by name with '(?P<candidates>.*)' on node (?P<hostname>.*)")

    def __init__(self, to, sender):
        Handler.__init__(self, to, sender)



def email(subject,body,to,sender):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['To'] = to
    msg['From'] = sender
    print 'Emailing this:\n====================\n%s' % str(msg)
    s = smtplib.SMTP('localhost')
    s.sendmail(sender, to, msg.as_string())


def watch(filename, to, sender):
    log = open(filename)
    log.seek(0,2) # Only want to look at *new* things
    handlers = [InvalidCertHandler(to, sender),
                WaitingCertHandler(to, sender),
                UnknownSlaveHandler(to, sender)]
    while True:
        try:
            log = open(filename)
            log.seek(0,2) # Only want to look at *new* things
            while True:
                try:
                    data = log.readline().strip()
                    if data == '':
                        time.sleep(0.5)
                    for i in handlers:
                        i.check(data)
                except IOError:
                    if not f.closed():
                        f.close()
        except IOError:
            time.sleep(0.5)
            pass

def main():
    sender = '%s@%s' % (os.getlogin(), socket.gethostname())
    if len(sys.argv) != 3:
        print "usage: %s /var/log/messages user@host.to.send.to" % sys.argv[0]
        exit(1)
    else:
        print "Watching %s" % sys.argv[1]
        watch(sys.argv[1], sys.argv[2], sender)


if __name__ == "__main__":
    # should probably daemonize and write logs (properly) to
    # the syslog
    main()

