#!/usr/bin/python

import configparser
import argparse
import sys
import os

from ovh import Client as OvhClient
from ovh import API_READ_WRITE
from ovh import exceptions

def authenticate(endpoint, applicationKey, applicationSecret):

    kwargs = {
      "endpoint"           : endpoint,
      "application_key"    : applicationKey,
      "application_secret" : applicationSecret,
    }

    ApiClientHandle = OvhClient(**kwargs)

    ck = ApiClientHandle.new_consumer_key_request()
    ck.add_rules(API_READ_WRITE, "/dedicated/server/*")
    ck.add_rules(API_READ_WRITE, "/dedicated/server")
    ck.add_rules(API_READ_WRITE, "/me/*")
    ck.add_rules(API_READ_WRITE, "/me")
    validation = ck.request()

    print("Please visit %s to authenticate" % validation['validationUrl'])
    input("and press Enter to continue...")

    return (ApiClientHandle, validation["consumerKey"])

def load_script(script):

    dirname = os.path.dirname(__file__)
    filename = os.path.join(dirname, script)

    with open(filename, "r") as script_file :
        lines = script_file.read()

    return lines

def upload_ipxe_script(client, name, content):

    try :
        client.get("/me/ipxeScript/%s" % name)
    except exceptions.ResourceNotFoundError as e :
        client.post("/me/ipxeScript",
            description = "%s IPXE script" % name,
            name = name,
            script = content
        )

    print("IPXE script %s successfully created" % name)

def get_ipxe_script_id(client, name):

    servers = client.get("/dedicated/server")

    if not servers :
        raise exceptions.ResourceNotFoundError("No dedicated server found")

    for server in servers :
        netboots = client.get("/dedicated/server/%s/boot" % server, bootType = "ipxeCustomerScript")

        for netboot_id in netboots :
            netboot = client.get("/dedicated/server/%s/boot/%s" % (server, netboot_id))

            if netboot["kernel"] == name :
                return netboot_id

    raise exceptions.ResourceNotFoundError("No netboot found for name %s" % name)


if __name__ == '__main__':

    # Parse arguments
    parser = argparse.ArgumentParser(description='Process OVHcloud Ironic APIv6 driver config file and generate the configuration.')
    parser.add_argument("file", help="Configuration file to process")
    args = parser.parse_args()

    # Load configuration from file
    config = configparser.ConfigParser()
    config.read(args.file)

    # Read required values
    try :
        applicationKey    = config['APIv6']['application_key']
        applicationSecret = config['APIv6']['application_secret']
        endpoint          = config['APIv6']['endpoint']
    except KeyError as e :
        print("Missing key in config file section APIv6 : "+str(e), file=sys.stderr)
        sys.exit(1)

    try :
        poweroff_name = config['IPXE_poweroff']['name']
        poweroff_file = config['IPXE_poweroff']['file']
    except KeyError as e :
        print("Missing key in config file section IPXE_poweroff : "+str(e), file=sys.stderr)
        sys.exit(1)

    try :
        boot_name = config['IPXE_boot']['name']
        boot_file = config['IPXE_boot']['file']
    except KeyError as e :
        print("Missing key in config file section IPXE_boot : "+str(e), file=sys.stderr)
        sys.exit(1)

    # Read files
    try :
        poweroff_script = load_script(poweroff_file)
        boot_script     = load_script(boot_file)
    except Exception as e :
        print("Cannot load IPXE script file : "+str(e), file=sys.stderr)
        sys.exit(1)

    # Authenticate
    try :
        client, consumerKey = authenticate(endpoint, applicationKey, applicationSecret)
        resp = client.get("/me")
    except Exception as e :
        print("Error during API call : "+str(e), file=sys.stderr)
        sys.exit(1)
    else :
        print("Successfully authenticated as %s (%s %s)" % (resp["nichandle"], resp["firstname"], resp["name"]))

    try :
        upload_ipxe_script(client, poweroff_name, poweroff_script)
        upload_ipxe_script(client, boot_name, boot_script)
    except Exception as e :
        print("Error during IPXE script deployment : "+str(e), file=sys.stderr)
        sys.exit(1)

    try :
        poweroff_id = get_ipxe_script_id(client, poweroff_name)
        boot_id     = get_ipxe_script_id(client, boot_name)
    except Exception as e :
        print("Error during IPXE script ID retrieval : "+str(e), file=sys.stderr)
        sys.exit(1)

    print("""
          Please, insert the following lines in your /etc/ironic/ironic.conf file

          [ovhapi]
          consumer_key = %s
          application_key = %s
          application_secret = %s
          endpoint = %s
          poweroff_script_id = %s
          boot_script_id = %s

          """ % (consumerKey, applicationKey, applicationSecret, endpoint, poweroff_id, boot_id))
