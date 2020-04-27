# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_log import log

from ironic.common import boot_devices
from ironic.common import exception
from ironic.drivers import base
from ironic.drivers.modules.ovhapi import client as ovh_client
from ironic.drivers.modules.ovhapi import common as ovh_common


LOG = log.getLogger(__name__)


class OvhApiManagement(base.ManagementInterface):

    def __init__(self):
        """Initialize the OVH power interface."""
        super(OvhApiManagement, self).__init__()
        self._client = ovh_client.BaseClient()

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

    def get_supported_boot_devices(self, task):
        """Get a list of the supported boot devices.

        :param task: a task from TaskManager.
        :returns: A list with the supported boot devices defined
                  in :mod:`ironic.common.boot_devices`.

        """
        return [boot_devices.PXE, boot_devices.DISK]

    def set_boot_device(self, task, device, persistent=False):
        """Set the boot device for a node.

        Set the boot device to use on next reboot of the node.

        :param task: a task from TaskManager.
        :param device: the boot device, one of the supported devices
                       listed in :mod:`ironic.common.boot_devices`.
        :param persistent: Boolean value. True if the boot device will
                           persist to all future boots, False if not.
                           Default: False.
        :raises: InvalidParameterValue if an invalid boot device is
                 specified.
        """
        server_name = task.node.driver_info['server_name']
        LOG.debug('Setting boot device to %(target)s requested for server '
                  '%(server)s with ovhapi management.',
                  {'target': device, 'server': server_name})
        if device == boot_devices.DISK:
            self._client.boot_on_disk(server_name)
            return
        elif device == boot_devices.PXE:
            self._client.chain_boot(server_name)
            return

        supported = self.get_supported_boot_devices(task)
        raise exception.InvalidParameterValue(
            _("Invalid boot device %(dev)s specified, supported are "
                "%(supported)s.") % {'dev': device,
                                     'supported': ', '.join(supported)})

    def get_boot_device(self, task):
        server_name = task.node.driver_info['server_name']
        if self._client.is_set_to_boot_on_disk(server_name):
            return {'boot_device': boot_devices.DISK, 'persistent': True}
        return {'boot_device': boot_devices.PXE, 'persistent': True}

    def get_sensors_data(self, task):
        return {}
