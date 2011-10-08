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


invalid_cert = re.compile('(?P<datetime>\w*\W*\d* \d*:\d*:\d*) (?P<p_master>[\w.\-_]*) puppetmasterd\[\d*\]: Certificate request does not match existing certificate; run \'(?P<suggestion>.*)\'.')
waiting_cert = re.compile('(?P<datetime>\w*\W*\d* \d*:\d*:\d*) (?P<p_master>[\w.\-_]*) puppetmasterd\[\d*\]: Host (?P<hostname>[\w\d\-_.]*) has a waiting certificate request')
suggestion_parse = re.compile('puppetca --clean (?P<hostname>[\w\d\-._]*)')

def email(subject,body,to='jhford@mozilla.com', sender=None):
    if sender is None:
        sender = '%s@%s' % (os.getlogin(), socket.gethostname())
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['To'] = to
    msg['From'] = sender
    print 'Emailing this:\n====================\n%s' % str(msg)
    s = smtplib.SMTP('localhost')
    s.sendmail(sender, to, msg.as_string())

def handle_invalid_cert(p_master, datetime, suggestion):
    hostname = suggestion_parse.match(suggestion).group("hostname")
    subprocess.call(['puppetca', '--clean', hostname])
    subject = "[%s] %s has invalid cert" % (p_master, hostname)
    body = """The puppet slave '%s' has an invalid puppet cert.
I tried cleaning it up manually, but I didn't check return codes.
Please make sure that this was done properly.  I won't automatically
try to sign a slave for security, so please sign it yourself!""" %hostname
    email(subject,body)


def handle_waiting_cert(p_master, datetime, hostname):
    subject = "[%s] %s is waiting to be signed" % (p_master, hostname)
    body = """The puppet slave '%s' has a waiting puppet signing request
I won't automatically try to sign a slave for security, so please
sign it yourself!""" %hostname
    email(subject,body)


def process_line(line):
    m = invalid_cert.match(line)
    if m:
        handle_invalid_cert(
            m.group("p_master"),
            m.group("datetime"),
            m.group("suggestion")
        )
        return True
    m = waiting_cert.match(line)
    if m:
        handle_waiting_cert(
            m.group("p_master"),
            m.group("datetime"),
            m.group("hostname")
        )
        return True


def watch(filename):
    log = open(filename)
    log.seek(0,2) # Only want to look at *new* things
    while True:
        try:
            data = log.readline().strip()
            if data == '':
                time.sleep(0.5)
            process_line(data)
        except IOError:
            log = open(filename)
            log.seek(0,2) # Only want to look at *new* things
    log.close()

def main():
    if len(sys.argv) != 2:
        print "usage: %s /var/log/messages" % sys.argv[0]
        exit(1)
    else:
        print "Watching %s" % sys.argv[1]
        watch(sys.argv[1])


if __name__ == "__main__":
    main()

