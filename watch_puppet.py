#!/usr/bin/env python

import sys
import re
import subprocess
import time

invalid_cert = re.compile('(?P<datetime>\w* \d* \d*:\d*:\d*) (?P<p_master>[\w.\-_]*) puppetmasterd\[\d*\]: Certificate request does not match existing certificate; run \'(?P<suggestion>.*)\'.')
waiting_cert = re.compile('(?P<datetime>\w* \d* \d*:\d*:\d*) (?P<p_master>[\w.\-_]*) puppetmasterd\[\d*\]: Host (?P<hostname>[\w\d\-_.]*) has a waiting certificate request')
suggestion_parse = re.compile('puppetca --clean (?P<hostname>[\w\d\-._]*)')

def email(subject,body):
    print 'S: %s' % subject
    print body

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
    try:
        while True:
            data = log.readline().strip()
            if data == '':
                time.sleep(0.5)
            process_line(data)
    except IOError:
        log = open(filename)
    log.close()

def main():
    if len(sys.argv) != 2:
        print >> sys.stderr, "usage: %s /var/log/messages" % sys.argv[0]
        exit(1)
    else:
        print "Watching %s" % sys.argv[1]
        watch(sys.argv[1])


if __name__ == "__main__":
    main()