#!/usr/bin/python 
import json
import os
import time
import datetime
import argparse
import uuid
import subprocess
import sys
import textwrap
import re
import math
import distutils.dir_util
import distutils.file_util
import shutil
import random
import glob
import copy
import numbers

from os.path import expanduser

import yaml
import json
from jinja2 import Environment, FileSystemLoader, Template
import base64
import tempfile
import urlparse

from shutil import copyfile, copytree
import urllib
import socket
sys.path.append("utils")
import utils
from utils import tolist

verbose = False

from az_params import *



def init_config():
    config = {}
    for k,v in default_config_parameters.iteritems():
        config[ k ] = v
    return config

def merge_config( config1, config2, verbose ):
    for entry in config2:
        if entry in config1:
            if isinstance( config1[entry], dict): 
                if verbose:
                    print ("Merge entry %s " % entry )
                merge_config( config1[entry], config2[entry], verbose )
            else:
                if verbose:
                    print ("Entry %s == %s " % (entry, config2[entry] ) )
                config1[entry] = config2[entry]
        else:
            if verbose:
                print ("Entry %s == %s " % (entry, config2[entry] ) )
            config1[entry] = config2[entry]

# resource_group_name is cluster_name + ResGrp
def update_config(config, genSSH=True):
    config["azure_cluster"]["resource_group_name"] = config["azure_cluster"]["cluster_name"]+"ResGrp"
    config["azure_cluster"]["vnet_name"] = config["azure_cluster"]["cluster_name"]+"-VNet"
    config["azure_cluster"]["storage_account_name"] = config["azure_cluster"]["cluster_name"]+"storage"
    config["azure_cluster"]["nsg_name"] = config["azure_cluster"]["cluster_name"]+"-nsg"
    config["azure_cluster"]["storage_account_name"] = config["azure_cluster"]["cluster_name"]+"storage"

    config["azure_cluster"]["sql_server_name"] = config["azure_cluster"]["cluster_name"]+"sqlserver"
    config["azure_cluster"]["sql_admin_name"] = config["azure_cluster"]["cluster_name"]+"sqladmin"
    config["azure_cluster"]["sql_database_name"] = config["azure_cluster"]["cluster_name"]+"sqldb"

    if "sql_admin_password" not in config["azure_cluster"]:
        config["azure_cluster"]["sql_admin_password"] = uuid.uuid4().hex+"12!AB"

    if (genSSH):
        if (os.path.exists('./deploy/sshkey/id_rsa.pub')):
            f = open('./deploy/sshkey/id_rsa.pub')
            config["azure_cluster"]["sshkey"] = f.read()
            f.close()
        else:
            os.system("mkdir -p ./deploy/sshkey")
            if not os.path.exists("./deploy/sshkey/azure_id_rsa"):
                os.system("ssh-keygen -t rsa -b 4096 -f ./deploy/sshkey/azure_id_rsa -P ''")
            f = open('./deploy/sshkey/azure_id_rsa.pub')
            config["azure_cluster"]["sshkey"] = f.read()
            f.close()

    return config


def create_vm(vmname, bIsWorker):
    vm_size = config["azure_cluster"]["worker_vm_size"] if bIsWorker else config["azure_cluster"]["infra_vm_size"]
    actual_location = get_location_string( config["azure_cluster"]["azure_location"])
    cmd = """
        az vm create --resource-group %s \
                 --name %s \
                 --image %s \
                 --generate-ssh-keys  \
                 --public-ip-address-dns-name %s \
                 --location %s \
                 --size %s \
                 --vnet-name %s \
                 --subnet mySubnet \
                 --nsg %s \
                 --public-ip-address-allocation static \
                 --admin-username %s \
                 --storage-sku %s \
                 --ssh-key-value "%s" 
        """ % (config["azure_cluster"]["resource_group_name"],
               vmname,
               config["azure_cluster"]["vm_image"],
               vmname,
               actual_location,
               vm_size,
               config["azure_cluster"]["vnet_name"],
               config["azure_cluster"]["nsg_name"],
               config["azure_cluster"]["default_admin_username"],
               config["azure_cluster"]["vm_storage_sku"],
               config["azure_cluster"]["sshkey"])
    if verbose:
        print(cmd)
    output = utils.exec_cmd_local(cmd)
    print (output)

def create_group():
    locations = tolist(config["azure_cluster"]["azure_location"])
    actual_location = get_location_string(locations[0] )
    cmd = """
        az group create --name %s --location %s 
        """ % (config["azure_cluster"]["resource_group_name"],actual_location)
    if verbose:
        print(cmd)
    output = utils.exec_cmd_local(cmd)
    print (output)


def create_sql():
    actual_location = get_location_string( config["azure_cluster"]["azure_location"] )
    cmd = """
        az sql server create --resource-group %s \
                 --location %s \
                 --name %s \
                 -u %s \
                 -p %s
        """ % (config["azure_cluster"]["resource_group_name"],
               actual_location,
               config["azure_cluster"]["sql_server_name"],
               config["azure_cluster"]["sql_admin_name"],
               config["azure_cluster"]["sql_admin_password"])
    if verbose:
        print(cmd)
    output = utils.exec_cmd_local(cmd)
    print (output)



    cmd = """
        az sql server firewall-rule create --resource-group %s \
                 --server %s \
                 --name All \
                 --start-ip-address 0.0.0.0 \
                 --end-ip-address 255.255.255.255
        """ % (config["azure_cluster"]["resource_group_name"],
               config["azure_cluster"]["sql_server_name"])
    if verbose:
        print(cmd)
    output = utils.exec_cmd_local(cmd)
    print (output)

def get_location_string( location ):
    if "az_location_mapping" in config and location in config["az_location_mapping"]:
        return config["az_location_mapping"][location]
    else:
        return location


def create_storage_account(name, sku, location):
    actual_location = get_location_string(location)
    cmd = """
        az storage account create \
            --name %s \
            --sku %s \
            --resource-group %s \
            --location %s 
        """ % (name,
               sku,
               config["azure_cluster"]["resource_group_name"],
               actual_location)
    if verbose:
        print(cmd)
    output = utils.exec_cmd_local(cmd)
    return output

def get_storage_keys( configGrp, location):
    cmd = """
        az storage account keys list \
            --account-name %s \
            --resource-group %s \
        """ % (configGrp[location]["fullname"],
               config["azure_cluster"]["resource_group_name"])
    if verbose:
        print(cmd)
    output = utils.exec_cmd_local(cmd)
    return output

def create_storage_container( location, name, configGrp, configContainer ):
    cmd = """
        az storage container create \
            --name %s \
            --account-key %s \
            --account-name %s \
        """ % ( name, configGrp[location]["keys"][0]["value"], configGrp[location]["fullname"] )
    if "public-access" in configContainer:
        cmd += " --public-access %s" % configContainer["public-access"]
    if verbose:
        print(cmd)
    output = utils.exec_cmd_local(cmd)
    return output

def add_cors( configGrp, location ):
    cmd = """
        az storage cors add \
            --method %s \
            --origins "*" \
            --services b \
            --allowed-headers "*" \
            --exposed-headers "*" \
            --max-age 200 \
            --timeout 200 \
            --account-key %s \
            --account-name %s \
        """ % ( configGrp["cors"], configGrp[location]["keys"][0]["value"], configGrp[location]["fullname"] )
    if verbose:
        print(cmd)
    output = utils.exec_cmd_local(cmd)
    return output

def create_storage_containers( configGrp, location ):
    if "containers" in configGrp:
        for name in configGrp["containers"]:
            configContainer = configGrp["containers"][name]
            create_storage_container( location, name, configGrp, configContainer )

def create_storage_with_config( configGrp, location ):
    storagename = configGrp["name"] + location
    output = create_storage_account( storagename, configGrp["sku"], location)
    if verbose: 
        print ( "Storage account %s" % output )
    configGrp[location] = json.loads( output )
    configGrp[location]["fullname"] = storagename
    output = get_storage_keys( configGrp, location )
    if verbose: 
        print ( "Storage keys %s" % output )   
    keyConfig = json.loads( output )
    configGrp[location]["keys"] = keyConfig
    create_storage_containers( configGrp, location )
    if "cors" in configGrp and configGrp["cors"]: 
        add_cors(configGrp, location)

# Fill in configuration with information on azure. 
def config_app_with_azure( configApp, azureConfig, provider ):
    locations = tolist( azureConfig["azure_cluster"]["azure_location"])
    if not ("Services" in configApp):
        configApp["Services"] = {}
    for location in locations:
        configGrp = azureConfig["azure_cluster"]["cdn"][location]
        if not (location in configApp["Services"]):
            configApp["Services"][location] = {}
        configAppGrp = configApp["Services"][location]
        if not ("cdns" in configAppGrp):
            configAppGrp["cdns"] = {}
        if provider not in configAppGrp["cdns"]:
            configAppGrp["cdns"][provider] = []
        if "primaryEndpoints" in configGrp and "blob" in configGrp["primaryEndpoints"]:
            configAppGrp["cdns"][provider].append ( configGrp["primaryEndpoints"]["blob"] )
        if "secondaryEndpoints" in configGrp and "blob" in configGrp["secondaryEndpoints"]:
            configAppGrp["cdns"][provider].append ( configGrp["secondaryEndpoints"]["blob"] )

# Fill in configuration with related to order server on azure. 
def config_order_with_azure( configOrder, azureConfig ):
    ()

def create_cdn_profile(name, sku, location):
    actual_location = get_location_string(location)
    cmd = """
        az cdn profile create \
            --name %s \
            --sku %s \
            --resource-group %s \
            --location %s 
        """ % (name,
               sku,
               config["azure_cluster"]["resource_group_name"],
               actual_location)
    if verbose:
        print(cmd)
    output = utils.exec_cmd_local(cmd)
    print (output)

def create_cdn_endpoint(name, origin, profilename):
    cmd = """
        az cdn endpoint create \
            --name %s \
            --origin %s \
            --profile-name %s \
            --resource-group %s 
        """ % (name,
               origin,
               profilename, 
               config["azure_cluster"]["resource_group_name"] )
    if verbose:
        print(cmd)
    output = utils.exec_cmd_local(cmd)
    if verbose:
        print (output)
    return (output)

def create_cdn_endpoint_with_config( cdnconfig, location):
    curConfig = cdnconfig[location] 
    if verbose:
        print yaml.safe_dump( curConfig, default_flow_style=False )
    curConfig["cdnprofile"] = cdnconfig["name"] + "profile" + location
    create_cdn_profile( curConfig["cdnprofile"], cdnconfig["cdnsku"], location)
    curConfig["cdnendpoint"] = cdnconfig["fullname"]
    primaryEndpoints = curConfig["primaryEndpoints"]
    blobendpoint = primaryEndpoints["blob"]
    parsed = urlparse.urlparse( blobendpoint )
    curConfig["cdnorigin"] = parsed.netloc
    output = create_cdn_endpoint( curConfig["cdnendpoint"], curConfig["cdnorigin"], curConfig["cdnprofile"], )
    curConfig["cdnconfig"] = json.loads( output )

def create_storage_group( locations, configGrp, docreate = True ):
    locations = tolist( config["azure_cluster"]["azure_location"])
    for location in locations:
        create_storage_with_config( configGrp, location )

def create_storage( docreate = True ):
    locations = tolist( config["azure_cluster"]["azure_location"])
    storages = tolist( config["azure_cluster"]["storages"] ) 
    for grp in storages:
        configGrp = config["azure_cluster"][grp]
        create_storage_group( locations, configGrp, docreate )
    cdnconfig = config["azure_cluster"]["cdn"]
    for location in locations:
        ()
        # disable CDN
        # create_cdn_endpoint_with_config( cdnconfig, location )
    with open("azure_cluster_file.yaml", "w") as outfile:
        yaml.safe_dump( config, outfile, default_flow_style=False)

def use_storage( args ):
    if len( args ) <= 0:
        print "Need storage group parameter"       
        return
    if args[0] in config["azure_cluster"]:
        configGrp = config["azure_cluster"][args[0]]
        use_storage_grp( configGrp, args[1:])
    else:
        print "There is no storage group %s" %args[0]
        print config["azure_cluster"]

def use_storage_grp( configGrp, args):
    if len( args ) <= 0:
        print "Need storage location parameter"
        return
    if args[0] in configGrp:
        configStorage = configGrp[args[0]]
        use_storage_loc( configStorage, args[1:])
    else:
        print "There is no storage location %s" %args[0]
        print configGrp

def use_storage_loc( configStorage, args):
    storagename = configStorage["fullname"]
    key = configStorage["keys"][0]["value"]
    os.environ["AZURE_STORAGE_KEY"] = key
    os.environ["AZURE_STORAGE_ACCOUNT"] = storagename
    print "Type the following ...."
    print( "export AZURE_STORAGE_KEY=%s" %key )
    print( "export AZURE_STORAGE_ACCOUNT=%s" %storagename)

def create_file_share():
    cmd = """
        az storage account show-connection-string \
            -n %s \
            -g %s \
            --query 'connectionString' \
            -o tsv
        """ % (config["azure_cluster"]["storage_account_name"],config["azure_cluster"]["resource_group_name"])
    output = utils.exec_cmd_local(cmd)
    print (output)

    cmd = """
        az storage share create \
            --name %s \
            --quota 2048 \
            --connection-string '%s'
        """ % (config["azure_cluster"]["file_share_name"],output)
    if verbose:
        print(cmd)
    output = utils.exec_cmd_local(cmd)
    print (output)


def create_vnet():
    cmd = """
        az network vnet create \
            --resource-group %s \
            --name %s \
            --address-prefix %s \
            --subnet-name mySubnet \
            --subnet-prefix %s
        """ %( config["azure_cluster"]["resource_group_name"],
               config["azure_cluster"]["vnet_name"],
               config["azure_cluster"]["vnet_range"],
               config["azure_cluster"]["vnet_range"])
    if verbose:
        print(cmd)
    output = utils.exec_cmd_local(cmd)
    print (output)

def create_nsg():
    cmd = """
        az network nsg create \
            --resource-group %s \
            --name %s
        """ %( config["azure_cluster"]["resource_group_name"],
               config["azure_cluster"]["nsg_name"])
    if verbose:
        print(cmd)
    output = utils.exec_cmd_local(cmd)
    print (output)

    cmd = """
        az network nsg rule create \
            --resource-group %s \
            --nsg-name %s \
            --name allowall \
            --protocol tcp \
            --priority 1000 \
            --destination-port-range 0-65535 \
            --access allow
        """ %( config["azure_cluster"]["resource_group_name"],
               config["azure_cluster"]["nsg_name"])
    output = utils.exec_cmd_local(cmd)
    print (output)

def delete_group():
    cmd = """
        az group delete -y --name %s 
        """ % (config["azure_cluster"]["resource_group_name"])
    if verbose:
        print(cmd)
    output = utils.exec_cmd_local(cmd)
    print (output)

def create_cluster():
    bSQLOnly = (config["azure_cluster"]["infra_node_num"]<=0)
    print "creating resource group..."
    create_group()
    if not bSQLOnly:
        print "creating storage account..."
        create_storage_account()
        print "creating file share..."
        create_file_share()
        print "creating vnet..."
        create_vnet()
        print "creating network security group..."
        create_nsg()
    print "creating sql server and database..."
    create_sql()

    print "creating VMs"
    for i in range(int(config["azure_cluster"]["infra_node_num"])):
        vmname = "%s-infra%02d" % (config["azure_cluster"]["cluster_name"], i+1)
        print "creating VM %s..." % vmname
        create_vm(vmname, False)
    for i in range(int(config["azure_cluster"]["worker_node_num"])):
        vmname = "%s-worker%02d" % (config["azure_cluster"]["cluster_name"], i+1)
        print "creating VM %s..." % vmname
        create_vm(vmname, True)

def gen_cluster_config(output_file_name, output_file=True):
    bSQLOnly = (config["azure_cluster"]["infra_node_num"]<=0)
    cmd = """
        az storage account show-connection-string \
            -n %s \
            -g %s \
            --query 'connectionString' \
            -o tsv
        """ % (config["azure_cluster"]["storage_account_name"],config["azure_cluster"]["resource_group_name"])
    output = utils.exec_cmd_local(cmd)
    reoutput = re.search('AccountKey\=.*$', output)
    file_share_key = None
    if reoutput is not None:
        file_share_key = reoutput.group(0).replace("AccountKey=","")

    reoutput = re.search('AccountName\=.*;', output)
    file_share_account_name = None
    if reoutput is not None:
        file_share_account_name = reoutput.group(0).replace("AccountName=","")[:-1]

    cc = {}
    cc["cluster_name"] = config["azure_cluster"]["cluster_name"]
    if not bSQLOnly:
        cc["etcd_node_num"] = config["azure_cluster"]["infra_node_num"]

    cc["sqlserver-hostname"] = "tcp:%s.database.windows.net" % config["azure_cluster"]["sql_server_name"]
    cc["sqlserver-username"] = config["azure_cluster"]["sql_admin_name"]
    cc["sqlserver-password"] = config["azure_cluster"]["sql_admin_password"]
    cc["sqlserver-database"] = config["azure_cluster"]["sql_database_name"]
    if not bSQLOnly:
        cc["admin_username"] = config["azure_cluster"]["default_admin_username"]
        cc["workFolderAccessPoint"] = "file://%s.file.core.windows.net/%s/work/" % (config["azure_cluster"]["storage_account_name"],config["azure_cluster"]["file_share_name"])
        cc["dataFolderAccessPoint"] = "file://%s.file.core.windows.net/%s/storage/" % (config["azure_cluster"]["storage_account_name"],config["azure_cluster"]["file_share_name"])
        cc["smbUsername"] = file_share_account_name
        cc["smbUserPassword"] = file_share_key
    cc["useclusterfile"] = True
    cc["deploydockerETCD"] = False
    cc["platform-scripts"] = "ubuntu"
    cc["basic_auth"] = "%s,admin,1000" % uuid.uuid4().hex[:7]
    if not bSQLOnly:
        cc["network"] = {"domain":"%s.cloudapp.azure.com" % config["azure_cluster"]["azure_location"]}
    cc["machines"] = {}
    for i in range(int(config["azure_cluster"]["infra_node_num"])):
        vmname = "%s-infra%02d" % (config["azure_cluster"]["cluster_name"], i+1)
        cc["machines"][vmname]= {"role": "infrastructure"}
    for i in range(int(config["azure_cluster"]["worker_node_num"])):
        vmname = "%s-worker%02d" % (config["azure_cluster"]["cluster_name"], i+1)
        cc["machines"][vmname]= {"role": "worker"}
    if not bSQLOnly:
        # Require explicit authorization setting. 
        # cc["WinbindServers"] = []
        # cc["WebUIauthorizedGroups"] = ['MicrosoftUsers']
        cc["mountpoints"] = {"rootshare":{}}
        cc["mountpoints"]["rootshare"]["type"] = "azurefileshare"
        cc["mountpoints"]["rootshare"]["accountname"] = config["azure_cluster"]["storage_account_name"]
        cc["mountpoints"]["rootshare"]["filesharename"] = config["azure_cluster"]["file_share_name"]
        cc["mountpoints"]["rootshare"]["mountpoints"] = ""
        if file_share_key is not None:
            cc["mountpoints"]["rootshare"]["accesskey"] = file_share_key

    if output_file:
        print yaml.dump(cc, default_flow_style=False)
        with open(output_file_name, 'w') as outfile:
            yaml.dump(cc, outfile, default_flow_style=False)

    return cc

def delete_cluster():
    print "!!! WARNING !!! Resource group {0} will be deleted".format(config["azure_cluster"]["resource_group_name"])
    response = raw_input ("!!! WARNING !!! You are performing a dangerous operation that will permanently delete the entire Azure DL Workspace cluster. Please type (DELETE) in ALL CAPITALS to confirm the operation ---> ")
    if response == "DELETE":
        delete_group()

def run_command_old( args, command, nargs, parser ):
    if command =="create":
        create_cluster()

    elif command == "delete":
        delete_cluster()

    elif command == "genconfig":
        gen_cluster_config("cluster.yaml")

def run_command( args, command, nargs, parser ):
    if command =="group" and len(nargs) >= 1:
        if nargs[0] == "create":
            create_group()

        elif nargs[0] == "delete":
            delete_group()

    if command == "storage":
        if nargs[0] == "create":
            create_storage()
        elif nargs[0] == "use":
            use_storage( nargs[1:])

    elif command == "genconfig":
        () # gen_cluster_config("cluster.yaml")

if __name__ == '__main__':
    # the program always run at the current directory. 
    dirpath = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
    # print "Directory: " + dirpath
    os.chdir(dirpath)
    parser = argparse.ArgumentParser( prog='az_tools.py',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent('''\
Create and manage a Azure VM cluster.

Prerequest:
* Create config.yaml according to instruction in docs/deployment/azure/configure.md.

Command:
  group [manage azure resource group.]
    create: create azure resource group
    delete: delete azure resource group
  storage [manage azure storage account. ]
    create: create azure storage account.
    use: [type] [loc] use a certain azure storage. 
  delete Delete the Azure VM cluster. 
  genconfig Generate configuration files for Azure VM cluster. 
  ''') )

    parser.add_argument("--verbose", "-v", 
        help = "Enable verbose output during script execution", 
        action = "store_true"
        )

    parser.add_argument("command", 
        help = "See above for the list of valid command" )
    parser.add_argument('nargs', nargs=argparse.REMAINDER, 
        help="Additional command argument", 
        )
    args = parser.parse_args()
    command = args.command
    nargs = args.nargs

    if args.verbose:
        verbose = args.verbose
    config = init_config()
    # Cluster Config
    config_cluster = os.path.join(dirpath,"azure_cluster_file.yaml")
    # print "config_cluster === %s" %config_cluster
    if os.path.exists(config_cluster):
        tmpconfig = yaml.load(open(config_cluster)) 
        # print "tmpconfig == %s" % tmpconfig    
        if tmpconfig is not None:
            merge_config(config, tmpconfig, verbose)

    config_file = os.path.join(dirpath,"config.yaml")
    if os.path.exists(config_file):
        tmpconfig = yaml.load(open(config_file)) 
        if tmpconfig is not None and "cluster_name" in tmpconfig:
            config["azure_cluster"]["cluster_name"] = tmpconfig["cluster_name"]
        if tmpconfig is not None and "azure_cluster" in tmpconfig:
            merge_config( config["azure_cluster"], tmpconfig["azure_cluster"][config["azure_cluster"]["cluster_name"]], verbose )
            
        
    config = update_config(config)
    if verbose: 
        print (config)

#   with open(config_cluster, 'w') as outfile:
#     yaml.dump(config, outfile, default_flow_style=False)

    if "cluster_name" not in config["azure_cluster"] or config["azure_cluster"]["cluster_name"] is None:
        print ("Cluster Name cannot be empty")
        exit()
    run_command( args, command, nargs, parser)


