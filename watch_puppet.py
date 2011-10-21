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

def email(subject,body,to,sender):
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['To'] = to
    msg['From'] = sender
    print 'Emailing this:\n====================\n%s' % str(msg)
    s = smtplib.SMTP('localhost')
    s.sendmail(sender, to, msg.as_string())

def handle_invalid_cert(p_master, datetime, suggestion, to, sender):
    hostname = suggestion_parse.match(suggestion).group("hostname")
    subprocess.call(['puppetca', '--clean', hostname])
    subject = "[%s] %s has invalid cert" % (p_master, hostname)
    body = """The puppet slave '%s' has an invalid puppet cert.
I tried cleaning it up manually, but I didn't check return codes.
Please make sure that this was done properly.  I won't automatically
try to sign a slave for security, so please sign it yourself!""" %hostname
    email(subject,body,to,sender)


def handle_waiting_cert(p_master, datetime, hostname, to, sender):
    subject = "[%s] %s is waiting to be signed" % (p_master, hostname)
    body = """The puppet slave '%s' has a waiting puppet signing request
I won't automatically try to sign a slave for security, so please
sign it yourself!""" %hostname
    email(subject,body,to,sender)


def process_line(line, to, sender):
    m = invalid_cert.match(line)
    if m:
        handle_invalid_cert(
            m.group("p_master"),
            m.group("datetime"),
            m.group("suggestion"),
            to, sender
        )
        return True
    m = waiting_cert.match(line)
    if m:
        handle_waiting_cert(
            m.group("p_master"),
            m.group("datetime"),
            m.group("hostname"),
            to, sender
        )
        return True


def watch(filename, to, sender):
    log = open(filename)
    log.seek(0,2) # Only want to look at *new* things
    while True:
        try:
            data = log.readline().strip()
            if data == '':
                time.sleep(0.5)
            process_line(data, to, sender)
        except IOError:
            log = open(filename)
            log.seek(0,2) # Only want to look at *new* things
    log.close()

def main():
    sender = '%s@%s' % (os.getlogin(), socket.gethostname())
    if len(sys.argv) != 3:
        print "usage: %s /var/log/messages user@host.to.send.to" % sys.argv[0]
        exit(1)
    else:
        print "Watching %s" % sys.argv[1]
        watch(sys.argv[1], sys.argv[2], sender)


if __name__ == "__main__":
    main()

