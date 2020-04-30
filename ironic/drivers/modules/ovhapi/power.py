# Copyright (c) 2020, OVH SAS.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import time

from oslo_log import log as logging

from ironic.common import exception
from ironic.common.i18n import _
from ironic.common import states
from ironic.conf import CONF
from ironic.drivers import base
from ironic.drivers.modules.ovhapi import client as ovhclient

LOG = logging.getLogger(__name__)

REQUIRED_PROPERTIES = {
    'server_name': _("Server name (ex nsXXXXX.ip-aaa-bbb-ccc.eu).  Required."),
}

OPTIONAL_PROPERTIES = {}
COMMON_PROPERTIES = REQUIRED_PROPERTIES.copy()
COMMON_PROPERTIES.update(OPTIONAL_PROPERTIES)


class OvhApiPower(base.PowerInterface):

    def __init__(self):
        """Initialize the OVH power interface."""
        super(OvhApiPower, self).__init__()
        self._client = ovhclient.BaseClient()

    @METRICS.timer('OvhApiPower.get_supported_power_states')
    def get_power_state(self, task):
        """Gets the current power state.

        :param task: a TaskManager instance.
        :returns: one of :mod:`ironic.common.states` POWER_OFF, POWER_ON or
            ERROR.
        """
        return [states.POWER_OFF, states.POWER_ON, states.REBOOT]

    @METRICS.timer('OvhApiPower.set_power_state')
    @task_manager.require_exclusive_lock
    def set_power_state(self, task, power_state, timeout=None):
        """Sets the power state according to the requested state.

        :param task: Ironic task
        :param power_state: Requested power state
        """
        if power_state not in self.get_supported_power_states(task):
            raise exception.InvalidParameterValue(
                _("set_power_state called with an invalid power state: {}.")
                .format(power_state)
            )

        server_name = task.node.driver_info['server_name']

        try:
            if power_state == states.POWER_OFF:
                result = self._client.set_boot_script(
                    server_name, CONF.ovhapi.poweroff_script)
                result.raise_for_status()
                result = self._client.reboot_server(server_name)
                result.raise_for_status()
            elif power_state in (states.POWER_ON, states.REBOOT):
                result = self._client.set_boot_script(
                    server_name, CONF.ovhapi.boot_script)
                result.raise_for_status()
                result = self._client.reboot_server(server_name)
                result.raise_for_status()
        except Exception as e:
            LOG.error("Exception during reboot call: {}".format(e))
            raise e

        task.node.power_state = states.REBOOT

        content = result.json()
        task_id = content['taskId']
        LOG.info("OVH APIv6 reboot task created: #{}".format(task_id))

        # TODO(pgaxatte): prevent infinity loop
        while True:
            time.sleep(3)

            result = self._client.get_task(server_name, task_id)
            result.raise_for_status()

            content = result.json()
            task_id = content['taskId']
            status = content['status']

            if status in ("ovhError", "customerError"):
                LOG.error("OVH APIv6 reboot task #{} is in error state"
                          .format(task_id))
                task.node.power_state = states.ERROR
                break

            if status not in ("init", "todo", "doing"):
                LOG.info("OVH APIv6 reboot task #{} is done".format(task_id))
                task.node.power_state = power_state
                break

    @METRICS.timer('OvhApiPower.reboot')
    @task_manager.require_exclusive_lock
    def reboot(self, task, timeout=None):
        self.set_power_state(task, states.REBOOT)

    def get_properties(self):
        """Return the properties of the interface.

        :returns: dictionary of <property name>:<property description> entries.
        """
        return COMMON_PROPERTIES

    @METRICS.timer('OvhApiPower.validate')
    def validate(self, task):
        """Check that node.driver_info contains the requisite fields.

        :raises: MissingParameterValue if required parameters are missing.
        :raises: InvalidParameterValue if parameters are invalid.
        """

        info = task.node.driver_info or {}
        missing_info = [
            k for k in REQUIRED_PROPERTIES.keys() if not info.get(k)
        ]
        if missing_info:
            raise exception.MissingParameterValue(
                _("OVH-API driver requires the following parameters to be set "
                  "in node's driver_info: {}.").format(missing_info)
            )

        # Calling API to check if we have access to the server
        result = self._client.list_servers()
        serverList = result.json()

        # We have server list. Checking our server against it
        server = task.node.driver_info['server_name']

        if server not in serverList:
            raise exception.InvalidParameterValue(
                _("Server {} is not linked to this OVH account or does not "
                  "exist").format(server)
            )
