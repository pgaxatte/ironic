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

from oslo_log import log
import requests

from ironic.common import exception
from ironic.conf import CONF
from ironic.drivers.modules.ovhapi import common as ovh_common
from ironic.drivers.modules.ovhapi import ovh_base

LOG = log.getLogger(__file__)


class BaseClient(ovh_base.Api):

    def __init__(self):
        super(BaseClient, self).__init__(
            ovh_base.ENDPOINTS.get(CONF.ovhapi.endpoint),
            CONF.ovhapi.application_key,
            CONF.ovhapi.application_secret,
            CONF.ovhapi.consumer_key,
            CONF.debug
        )

        self._check_ipxe_script_exists(CONF.ovhapi.boot_script)

    def validate_task(self, task):
        """Checks that the task is valid.

        Checks that:
        - task.node.driver_info contains the requisite fields,
        - task.node.driver_info['server_name'] refers to an existing server

        :raises: MissingParameterValue if required parameters are missing.
        :raises: InvalidParameterValue if parameters are invalid.
        """
        info = task.node.driver_info or {}
        missing_info = [
            k for k in ovh_common.REQUIRED_PROPERTIES.keys() if not info.get(k)
        ]
        if missing_info:
            raise exception.MissingParameterValue(
                _("OVH-API driver requires the following parameters to be set "
                  "in node's driver_info: {}.").format(missing_info)
            )

        server = info.get('server_name')
        if server not in self.list_servers():
            raise exception.InvalidParameterValue(
                _("Server {} is not linked to this OVH account or does not "
                  "exist").format(server)
            )

    def _check_ipxe_script_exists(self, script_name):
        """Checks a certain ipxe script is present on the API.

        :raises: requests.exceptions.HTTPError if the script is not found
        """
        try:
            self.get("/me/ipxeScript/{}".format(script_name))
        # TODO(pgaxatte): catch custom Ironic exception from OvhBase._call
        except requests.exceptions.HTTPError as e:
            LOG.error("Could not retrieve ipxe script %(script)s: %(error)s",
                      {'script': script_name, 'error': e})
            raise e

    def list_servers(self):
        """Gets the list of servers for this account."""
        try:
            result = self.get("/dedicated/server").json()
            LOG.debug("Getting server list: %(result)s",
                      {'result': result})
        # TODO(pgaxatte): catch custom Ironic exception from OvhBase._call
        except requests.exceptions.HTTPError as e:
            LOG.error("Could not get the server list: %(error)s",
                      {'error': e})
            raise e
        return result

    def get_server(self, server_name):
        """Gets informations on a server.

        :param server_name: the name of the server to query
        """
        try:
            result = self.get(
                "/dedicated/server/{}".format(server_name)).json()
            LOG.debug("Getting server info on %(server)s: %(result)s",
                      {'server': server_name, 'result': result})
        # TODO(pgaxatte): catch custom Ironic exception from OvhBase._call
        except requests.exceptions.HTTPError as e:
            LOG.error("Could not get the server info for %(server)s: "
                      "%(error)s",
                      {'server': server_name, 'error': e})
            raise e
        return result

    def hard_reboot_server(self, server_name):
        """Reboots the server.

        :param server_name: the name of the server to reboot
        :returns: the task_id of the reboot
        """
        try:
            result = self.post(
                "/dedicated/server/{}/reboot".format(server_name),
                None
            ).json()
            LOG.debug("Hard rebooting server %(server)s: %(result)s",
                      {'server': server_name, 'result': result})
        # TODO(pgaxatte): catch custom Ironic exception from OvhBase._call
        except requests.exceptions.HTTPError as e:
            LOG.error("Could not reboot %(server)s: %(error)s",
                      {'server': server_name, 'error': e})
            raise e

        task_id = result['taskId']
        LOG.info("Reboot task created for server %(server)s: #%(task)s",
                 {'server': server_name, 'task': task_id})
        return task_id

    def get_task_status(self, server_name, task_id):
        try:
            result = self.get("/dedicated/server/{}/task/{}"
                              .format(server_name, task_id)).json()
            LOG.debug("Get server info for %(server)s: %(result)s",
                      {'server': server_name, 'result': result})
        # TODO(pgaxatte): catch custom Ironic exception from OvhBase._call
        except requests.exceptions.HTTPError as e:
            LOG.error("Could not get server info for %(server)s: %(error)s",
                      {'server': server_name, 'error': e})
            raise e

        status = result['status']
        LOG.info("Task %(task)s for server %(server)s is in status %(status)s",
                 {'server': server_name, 'task': task_id, 'status': status})
        return status

    def set_boot_id(self, server_name, boot_id):
        """Sets the server to point to the specified boot script

        :param server_name: the name of the server to configure
        :param boot_id: the ID of the script to use on next boot
        """
        try:
            self.put("/dedicated/server/{}".format(server_name),
                     {'bootId': boot_id})
            LOG.debug("Set boot_id to %(boot_id)s for server %(server)s",
                      {'server': server_name, 'boot_id': boot_id})
        # TODO(pgaxatte): catch custom Ironic exception from OvhBase._call
        except requests.exceptions.HTTPError as e:
            LOG.error("Could not set bootId for %(server)s to %(boot_id)s: "
                      "%(error)s",
                      {'server': server_name, 'boot_id': boot_id, 'error': e})
            raise e

    def get_ipxe_script_id(self, server_name, script_name):
        """Gets the ID of a ipxe script from its name for a given server.

        :raises: requests.exceptions.HTTPError if the API return an error
        :raises: Exception if not matching script is found
        :returns: the ID of the script
        """
        try:
            result = self.get(
                "/dedicated/server/{}/boot?bootType=ipxeCustomerScript"
                .format(server_name)
            ).json()
            LOG.debug("Get ipxeCustomerScript for %(server)s: %(result)s",
                      {'server': server_name, 'result': result})
        # TODO(pgaxatte): catch custom Ironic exception from OvhBase._call
        except requests.exceptions.HTTPError as e:
            LOG.error("Could not retrieve boot scripts for server %(server)s: "
                      "%(error)s",
                      {'server': server_name, 'error': e})
            raise e

        for boot_id in result:
            try:
                result = self.get(
                    "/dedicated/server/{}/boot/{}"
                    .format(server_name, boot_id)
                ).json()
                LOG.debug("Get boot info for %(server)s: %(result)s",
                          {'server': server_name, 'result': result})
            # TODO(pgaxatte): catch custom Ironic exception from OvhBase._call
            except requests.exceptions.HTTPError as e:
                LOG.warning("Could not get the description of bootId "
                            "%(boot_id)s for %(server)s. Skipping. Exception: "
                            "%(error)s",
                            {'server': server_name, 'boot_id': boot_id,
                             'error': e})
                continue

            # If this bootId corresponds to the script we are looking for,
            # return it
            if result.get("kernel", "") == script_name:
                LOG.debug("boot_id found %(server)s: %(script)s -> "
                          "%(boot_id)s",
                          {'server': server_name, 'script': script_name,
                           'boot_id': boot_id})
                return boot_id

        # TODO(pgaxatte): use a real custom exception
        e = Exception("No script %(script)s found for %(server)s",
                      {'script': script_name, 'server': server_name})
        LOG.error("Could not retrieve the ID of the script %(script)s: "
                  "%(error)s",
                  {'script': script_name, 'error': e})
        raise e

    def get_disk_boot_id(self, server_name):
        """Gets the boot ID for harddisk boot type a from its name for a given server.

        :raises: requests.exceptions.HTTPError if the API return an error
        :raises: Exception if not matching script is found
        :returns: the ID of the script
        """
        try:
            result = self.get(
                "/dedicated/server/{}/boot?bootType=harddisk"
                .format(server_name)
            ).json()
            LOG.debug("Get harddisk booot id for %(server)s: %(result)s",
                      {'server': server_name, 'result': result})
        # TODO(pgaxatte): catch custom Ironic exception from OvhBase._call
        except requests.exceptions.HTTPError as e:
            LOG.error("Could not retrieve boot script for server %(server)s: "
                      "%(error)s", {'server': server_name, 'error': e})
            raise e

        for boot_id in result:
            LOG.debug("Returning first harddisk boot id found for %(server)s. "
                      "Result=%(boot_id)s",
                      {'server': server_name, 'boot_id': boot_id})
            return boot_id

        # TODO(pgaxatte): use a real custom exception
        e = Exception("No id for harddisk boot found for %(server)s",
                      {'server': server_name})
        LOG.error("Could not get a harddisk boot id: %(error)s", {'error': e})
        raise e

    def chain_boot(self, server_name):
        """Sets the server to point to the iPXE chain boot script

        :param server_name: the name of the server to configure
        """
        LOG.debug("Setting %(server)s to iPXE chain script",
                  {'server': server_name})
        self.set_boot_id(
            server_name,
            self.get_ipxe_script_id(server_name, CONF.ovhapi.boot_script)
        )

    def poweroff(self, server_name):
        """Sets the server to point to the poweroff boot script

        :param server_name: the name of the server to configure
        """
        LOG.debug("Setting %(server)s to poweroff script",
                  {'server': server_name})
        self.set_boot_id(
            server_name,
            self.get_ipxe_script_id(server_name, CONF.ovhapi.poweroff_script)
        )

    def boot_on_disk(self, server_name):
        """Sets the server to boot on the disk.

        :param server_name: the name of the server to configure
        """
        LOG.debug("Setting %(server)s to boot on disk",
                  {'server': server_name})
        self.set_boot_id(
            server_name,
            self.get_disk_boot_id(server_name)
        )

    def is_set_to_boot_on_disk(self, server_name):
        """Checks if a server is set to boot on disk or not.

        :raises: requests.exceptions.HTTPError if the API return an error
        :raises: Exception if not matching script is found
        :returns: true if server is set to boot on disk, false otherwise
        """
        # Get the list of bootId of type harddisk
        try:
            disk_boot_ids = self.get(
                "/dedicated/server/{}/boot?bootType=harddisk"
                .format(server_name)
            ).json()
            LOG.debug("Get harddisk booot id for %(server)s: %(result)s",
                      {'server': server_name, 'result': disk_boot_ids})
        # TODO(pgaxatte): catch custom Ironic exception from OvhBase._call
        except requests.exceptions.HTTPError as e:
            LOG.error("Could not retrieve boot script for server %(server)s: "
                      "%(error)s", {'server': server_name, 'error': e})
            raise e

        # Check the current bootId is in this list
        boot_id = self.get_server(server_name)['bootId']
        return boot_id in disk_boot_ids
