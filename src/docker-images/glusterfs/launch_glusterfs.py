#!/usr/bin/python 
# launch gluster fs 
import time
import os
from datetime import datetime
import yaml
import logging
import logging.config
import argparser

def create_log( logdir ):
	if not os.path.exists( logdir ):
		os.system("mkdir -p " + logdir )
	curtime = datetime.utcnow()
	fname = os.path.join( logdir, str(curtime) + ".log" )
	
def start_glusterfs( logdir = '/var/log/glusterfs/launch' ):
	with open('logging.yaml') as f:
		logging_config = yaml.load(f)
		f.close()
		logging.config.dictConfig(logging_config)
	create_log( logdir )
	# set up logging to file - see previous section for more details
	logging.debug ("Start launch glusterfs ...." )




if __name__ == '__main__':
	parser = argparse.ArgumentParser( prog='launch_glusterfs.py',
		formatter_class=argparse.RawDescriptionHelpFormatter,
		description=textwrap.dedent('''\
Format, manage and deploy a glusterFS cluster.

Prerequest:
This command is expected to be executed on every glusterFS brick node.

Command:
  mkfs [dev] format & mount the glusterFS partition. 
  ''') )
	parser.add_argument("command", 
		help = "See above for the list of valid command" )
	parser.add_argument('nargs', nargs=argparse.REMAINDER, 
		help="Additional command argument", 
		)
	args = parser.parse_args()
	

	start_glusterfs()
	logging.debug( "End launch glusterfs, time ... " )
