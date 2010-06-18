#!/usr/bin/python
# vi: ts=4 expandtab
#
#    Copyright (C) 2009-2010 Canonical Ltd.
#
#    Author: Scott Moser <scott.moser@canonical.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License version 3, as
#    published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import subprocess
import sys

import cloudinit
import cloudinit.util as util
import time
import logging

def warn(str):
    sys.stderr.write(str)

def main():
    now = time.strftime("%a, %d %b %Y %H:%M:%S %z")
    try:
       uptimef=open("/proc/uptime")
       uptime=uptimef.read().split(" ")[0]
       uptimef.close()
    except IOError as e:
       warn("unable to open /proc/uptime\n")
       uptime = "na"

    msg = "cloud-init running: %s. up %s seconds" % (now, uptime)
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()

    cloudinit.logging_set_from_cfg_file()
    log = logging.getLogger()
    log.info(msg)

    # cache is not instance specific, so it has to be purged
    cloudinit.purge_cache()

    cloud = cloudinit.CloudInit()

    try:
        cloud.get_data_source()
    except Exception as e:
        print e
        sys.stderr.write("Failed to get instance data\n")
        sys.exit(1)

    # store the metadata
    cloud.update_cache()

    # parse the user data (ec2-run-userdata.py)
    try:
        cloud.sem_and_run("consume_userdata", "once-per-instance",
            cloud.consume_userdata,[],False)
    except:
        warn("consuming user data failed!\n")
        raise

    try:
        hostname = cloud.get_hostname()
        cloud.sem_and_run("set_hostname", "once-per-instance",
            set_hostname, [ hostname ], False)
    except:
        warn("failed to set hostname\n")

    #print "user data is:" + cloud.get_user_data()

    # set the defaults (like what ec2-set-defaults.py did)
    try:
        cloud.sem_and_run("set_defaults", "once-per-instance",
            set_defaults,[ cloud ],False)
    except:
        warn("failed to set defaults\n")

    # finish, send the cloud-config event
    cloud.initctl_emit()

    sys.exit(0)

def set_defaults(cloud):
    apply_locale(cloud.get_locale())
    
def apply_locale(locale):
    subprocess.Popen(['locale-gen', locale]).communicate()
    subprocess.Popen(['update-locale', locale]).communicate()

    util.render_to_file('default-locale', '/etc/default/locale', \
        { 'locale' : locale })

def set_hostname(hostname):
    subprocess.Popen(['hostname', hostname]).communicate()
    f=open("/etc/hostname","wb")
    f.write("%s\n" % hostname)
    f.close()

if __name__ == '__main__':
    main()
