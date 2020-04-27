from oslo_log import log as logging

from ironic.conf import CONF
from ironic.common import states, exception
from ironic.common.i18n import _
from ironic.conductor import task_manager
from ironic.drivers import base
from ironic.drivers.modules.ovhapi import client as ovhclient

import os
import subprocess
import time

LOG = logging.getLogger(__name__)

OVHCLIENT = ovhclient.BaseClient()

REQUIRED_PROPERTIES = {
  'server_name': _("Server name (ex nsXXXXX.ip-aaa-bbb-ccc.eu).  Required."),
}

OPTIONAL_PROPERTIES = { }
COMMON_PROPERTIES = REQUIRED_PROPERTIES.copy()
COMMON_PROPERTIES.update(OPTIONAL_PROPERTIES)


class OvhApiPower(base.PowerInterface):

  #
  # PowerInterface implementation
  #

  def get_power_state(self, task):
    """Gets the current power state.

    :param task: a TaskManager instance.
    :returns: one of :mod:`ironic.common.states` POWER_OFF, POWER_ON or ERROR.
    """
    return task.node.power_state

  def set_power_state(self, task, power_state, timeout=None):
    """Setting power state according to the requested state

    :param task: Ironic task
    :param power_state: Requested power state
    """
    if power_state not in self.get_supported_power_states(task):
      raise exception.InvalidParameterValue( _("set_power_state called with an invalid power state: %s.") % power_state)

    serverName = task.node.driver_info['server_name']
    poweroff_bootId = CONF.ovhapi.poweroff_script_id
    boot_bootId = CONF.ovhapi.boot_script_id

    try :
        if  power_state == states.POWER_OFF :
            result = OVHCLIENT.set_bootId(serverName, poweroff_bootId)
            result.raise_for_status()
            result = OVHCLIENT.reboot_server(serverName)
            result.raise_for_status()
        elif power_state == states.POWER_ON :
            result = OVHCLIENT.set_bootId(serverName, boot_bootId)
            result.raise_for_status()
            result = OVHCLIENT.reboot_server(serverName)
            result.raise_for_status()
        elif power_state == states.REBOOT :
            result = OVHCLIENT.set_bootId(serverName, boot_bootId)
            result.raise_for_status()
            result = OVHCLIENT.reboot_server(serverName)
            result.raise_for_status()
    except Exception as e :
        LOG.error("Exception during reboot call : "+str(e))
        raise e

    task.node.power_state = states.REBOOT

    content = result.json()
    taskId = content['taskId']
    LOG.info("OVH APIv6 reboot task created : #"+str(taskId))

    while True :
        time.sleep(3)

        result = OVHCLIENT.get_task(serverName, taskId)
        result.raise_for_status()

        content = result.json()
        taskId = content['taskId']
        status = content['status']

        if status in ["ovhError", "customerError"] :
            LOG.error("OVH APIv6 reboot task #"+str(taskId)+" is in error state")
            task.node.power_state = states.ERROR
            break

        if status not in ["init", "todo", "doing"] :
            LOG.info("OVH APIv6 reboot task #"+str(taskId)+" is done")
            task.node.power_state = power_state
            break

  def reboot(self, task, timeout=None):
    self.set_power_state(task, states.REBOOT)

  #
  # BaseInterface implementation
  #

  def get_properties(self):
    """Return the properties of the interface.

    :returns: dictionary of <property name>:<property description> entries.
    """
    return COMMON_PROPERTIES


  def validate(self, task):
    """Check that node.driver_info contains the requisite fields.

    :raises: MissingParameterValue if required parameters are missing.
    :raises: InvalidParameterValue if parameters are invalid.
    """

    info = task.node.driver_info or {}
    missing_info = [key for key in REQUIRED_PROPERTIES if not info.get(key)]
    if missing_info:
      raise exception.MissingParameterValue(_("Ovh-API driver requires the following parameters to be set in node's driver_info: %s.") % missing_info)

    #
    # Calling API to check if we have access to the server
    #

    result = OVHCLIENT.list_servers()
    serverList = result.json()

    #
    # We have server list. Checking our server against it
    #

    server = task.node.driver_info['server_name']

    if server not in serverList :
      raise exception.InvalidParameterValue(_("Server %s is not linked to this OVH account or does not exist") % server)
