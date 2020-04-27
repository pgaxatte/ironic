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
from ironic.conductor import task_manager
from ironic.drivers import base
from ironic.drivers.modules.ovhapi import client as ovh_client
from ironic.drivers.modules.ovhapi import common as ovh_common

LOG = logging.getLogger(__name__)


class OvhApiPower(base.PowerInterface):

    def __init__(self):
        """Initialize the OVH power interface."""
        super(OvhApiPower, self).__init__()
        self._client = ovh_client.BaseClient()

    def get_power_state(self, task):
        """Gets the current power state.

        :param task: a TaskManager instance.
        :returns: one of :mod:`ironic.common.states` POWER_OFF, POWER_ON or
            ERROR.
        """
        return task.node.power_state

    @task_manager.require_exclusive_lock
    def set_power_state(self, task, power_state, timeout=None):
        """Sets the power state according to the requested state.

        The POWEROFF state requires that we set a boot script that just execute
        the 'poweroff' command from PXE and reboots using it.

        Any other state just instructs OVH API to reboot the server.

        :param task: Ironic task
        :param power_state: Requested power state
        """
        if power_state not in self.get_supported_power_states(task):
            raise exception.InvalidParameterValue(
                _("set_power_state called with an invalid power state: {}.")
                .format(power_state)
            )

        server_name = task.node.driver_info['server_name']

        LOG.debug("Setting power state to %(state)s for %(server)s",
                  {'state': power_state, 'server': server_name})

        previous_boot_id = None
        if power_state == states.POWER_OFF:
            previous_boot_id = self._client.get_server(server_name)['bootId']
            LOG.debug("Saving previous bootId (%(boot_id)s) before poweroff",
                      {'boot_id': previous_boot_id})
            self._client.poweroff(server_name)

        try:
            task_id = self._client.hard_reboot_server(server_name)

            task.node.power_state = states.REBOOT

            # TODO(pgaxatte): prevent infinity loop
            while True:
                time.sleep(3)

                status = self._client.get_task_status(server_name, task_id)
                LOG.debug("Reboot task #%(task)s is in state %(status)s",
                          {'task': task_id, 'status': status})

                if status in ("ovhError", "customerError"):
                    LOG.error("Reboot task #%(task)s is in error state",
                              {'task': task_id})
                    task.node.power_state = states.ERROR
                    break

                if status not in ("init", "todo", "doing"):
                    LOG.info("Reboot task #%(task)s is done",
                             {'task': task_id})
                    task.node.power_state = power_state
                    break
        finally:
            # Always reset the bootId if we had to change it to power off
            if previous_boot_id is not None:
                LOG.debug("Restoring bootId to previous value: %(boot_id)s",
                          {'boot_id': previous_boot_id})
                self._client.set_boot_id(server_name, previous_boot_id)

    @task_manager.require_exclusive_lock
    def reboot(self, task, timeout=None):
        self.set_power_state(task, states.REBOOT)

    def get_properties(self):
        """Return the properties of the interface.

        :returns: dictionary of <property name>:<property description> entries.
        """
        return ovh_common.COMMON_PROPERTIES

    def validate(self, task):
        """Check that the task is valid.

        :raises: MissingParameterValue if required parameters are missing.
        :raises: InvalidParameterValue if parameters are invalid.
        """
        self._client.validate_task(task)
