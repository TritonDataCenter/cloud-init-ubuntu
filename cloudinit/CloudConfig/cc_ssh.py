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
import cloudinit.util as util
import cloudinit.SshUtil as sshutil
import os
import glob
import subprocess

DISABLE_ROOT_OPTS="no-port-forwarding,no-agent-forwarding,no-X11-forwarding,command=\"echo \'Please login as the user \\\"$USER\\\" rather than the user \\\"root\\\".\';echo;sleep 10\""


global_log = None

def handle(name,cfg,cloud,log,args):
    global global_log
    global_log = log

    # remove the static keys from the pristine image
    for f in glob.glob("/etc/ssh/ssh_host_*_key*"):
        try: os.unlink(f)
        except: pass

    if cfg.has_key("ssh_keys"):
        # if there are keys in cloud-config, use them
        key2file = {
            "rsa_private" : ("/etc/ssh/ssh_host_rsa_key", 0600),
            "rsa_public"  : ("/etc/ssh/ssh_host_rsa_key.pub", 0644),
            "dsa_private" : ("/etc/ssh/ssh_host_dsa_key", 0600),
            "dsa_public"  : ("/etc/ssh/ssh_host_dsa_key.pub", 0644),
            "ecdsa_private" : ("/etc/ssh/ssh_host_ecdsa_key", 0600),
            "ecdsa_public"  : ("/etc/ssh/ssh_host_ecdsa_key.pub", 0644),
        }

        for key,val in cfg["ssh_keys"].items():
            if key2file.has_key(key):
                util.write_file(key2file[key][0],val,key2file[key][1])

        priv2pub = { 'rsa_private':'rsa_public', 'dsa_private':'dsa_public',
            'ecdsa_private': 'ecdsa_public', }

        cmd = 'o=$(ssh-keygen -yf "%s") && echo "$o" root@localhost > "%s"'
        for priv,pub in priv2pub.iteritems():
            if pub in cfg['ssh_keys'] or not priv in cfg['ssh_keys']: continue
            pair=(key2file[priv][0], key2file[pub][0])
            subprocess.call(('sh', '-xc', cmd % pair))
            log.debug("generated %s from %s" % pair)
    else:
        # if not, generate them
        genkeys ='ssh-keygen -f /etc/ssh/ssh_host_rsa_key -t rsa -N ""; '
        genkeys+='ssh-keygen -f /etc/ssh/ssh_host_dsa_key -t dsa -N ""; '
        genkeys+='ssh-keygen -f /etc/ssh/ssh_host_ecdsa_key -t ecdsa -N ""; '
        subprocess.call(('sh', '-c', "{ %s } </dev/null" % (genkeys)))

    try:
        user = util.get_cfg_option_str(cfg,'user')
        disable_root = util.get_cfg_option_bool(cfg, "disable_root", True)
        disable_root_opts = util.get_cfg_option_str(cfg, "disable_root_opts",
            DISABLE_ROOT_OPTS)
        keys = cloud.get_public_ssh_keys()

        if cfg.has_key("ssh_authorized_keys"):
            cfgkeys = cfg["ssh_authorized_keys"]
            keys.extend(cfgkeys)

        apply_credentials(keys,user,disable_root, disable_root_opts)
    except:
        util.logexc(log)
        log.warn("applying credentials failed!\n")

    send_ssh_keys_to_console()

def send_ssh_keys_to_console():
    subprocess.call(('/usr/lib/cloud-init/write-ssh-key-fingerprints',))

def apply_credentials(keys, user, disable_root, disable_root_opts=DISABLE_ROOT_OPTS, log=global_log):
    keys = set(keys)
    if user:
        sshutil.setup_user_keys(keys, user, '', log)
 
    if disable_root:
        key_prefix = disable_root_opts.replace('$USER', user)
    else:
        key_prefix = ''

    sshutil.setup_user_keys(keys, 'root', key_prefix, log)

