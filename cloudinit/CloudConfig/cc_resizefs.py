# vi: ts=4 expandtab
#
#    Copyright (C) 2011 Canonical Ltd.
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
import cloudinit.util as util
import subprocess
import traceback
import os
import stat
import tempfile

def handle(name,cfg,cloud,log,args):
    if len(args) != 0:
        resize_root = False
        if str(value).lower() in [ 'true', '1', 'on', 'yes']:
            resize_root = True
    else:
        resize_root = util.get_cfg_option_bool(cfg,"resize_rootfs",True)

    if not resize_root: return

    # this really only uses the filename from mktemp, then we mknod into it
    (fd, devpth) = tempfile.mkstemp()
    os.unlink(devpth)
    os.close(fd)
    
    try:
       st_dev=os.stat("/").st_dev
       dev=os.makedev(os.major(st_dev),os.minor(st_dev))
       os.mknod(devpth, 0400 | stat.S_IFBLK, dev)
    except:
        if util.islxc():
            log.debug("inside lxc, ignoring mknod failure in resizefs")
            return
        log.warn("Failed to make device node to resize /")
        raise

    cmd = [ 'blkid', '-c', '/dev/null', '-sTYPE', '-ovalue', devpth ]
    try:
        (fstype,err) = util.subp(cmd)
    except subprocess.CalledProcessError as e:
        log.warn("Failed to get filesystem type of maj=%s, min=%s via: %s" %
            (os.major(st_dev), os.minor(st_dev), cmd))
        log.warn("output=%s\nerror=%s\n", e.output[0], e.output[1])
        os.unlink(devpth)
        raise

    log.debug("resizing root filesystem (type=%s, maj=%i, min=%i)" % 
        (fstype.rstrip("\n"), os.major(st_dev), os.minor(st_dev)))

    if fstype.startswith("ext"):
        resize_cmd = [ 'resize2fs', devpth ]
    elif fstype == "xfs":
        resize_cmd = [ 'xfs_growfs', devpth ]
    else:
        os.unlink(devpth)
        log.debug("not resizing unknown filesystem %s" % fstype)
        return

    try:
        (out,err) = util.subp(resize_cmd)
    except subprocess.CalledProcessError as e:
        log.warn("Failed to resize filesystem (%s)" % resize_cmd)
        log.warn("output=%s\nerror=%s\n", e.output[0], e.output[1])
        os.unlink(devpth)
        raise

    os.unlink(devpth)
    return
