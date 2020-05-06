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

from ironic.common import states
from ironic.conf import CONF
from ironic.drivers.modules import deploy_utils
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

        self._check_ipxe_script_exists(CONF.ovhapi.poweroff_script)
        self._check_ipxe_script_exists(CONF.ovhapi.boot_script)

    def _check_ipxe_script_exists(self, script_name):
        """Checks a certain ipxe script is present on the API.

        :raises: requests.exceptions.HTTPError if the script is not found
        """
        try:
            result = self.get("/me/ipxeScript/{}".format(script_name))
            result.raise_for_status()
        except requests.exceptions.HTTPError as e:
            LOG.error("Could not retrieve ipxe script named '{}': {}"
                      .format(script_name, e))
            raise e

    def list_servers(self):
        """Gets the list of servers for this account.

        :param server_name: the name of the server to reboot
        """
        return self.get("/dedicated/server")

    def reboot_server(self, server_name):
        """Reboots the server.

        :param server_name: the name of the server to reboot
        """
        return self.post("/dedicated/server/{}/reboot".format(server_name),
                         None)

    def set_boot_script(self, task, server_name, script_name):
        """Sets the server to point on the specified boot script
        Or harddisk according to the task

        :param server_name: the name of the server to configure
        :param script_name: the name of the script to use on next boot
        """

        node = task.node

        boot_option = deploy_utils.get_boot_option(node)

        boot_id = None

        LOG.debug("YANN Current node provision_state before boot for {}. Result={}"
                  .format(server_name, node.provision_state))
        LOG.debug("YANN Current task {}"
                  .format(task))
        LOG.debug("YANN Current node {}"
                  .format(node))
        LOG.debug("YANN Current boot_option {}"
                  .format(boot_option))

        if node.provision_state == states.DEPLOYDONE:
            boot_id = self.get_disk_boot_id(server_name)
        else:
            boot_id = self.get_ipxescript_boot_id(server_name, script_name)

        LOG.debug("YANN Boot server on id for {}. Result={}"
                  .format(server_name, boot_id))

        return self.put("/dedicated/server/{}"
                        .format(server_name), {'bootId': boot_id})

    def get_task(self, server_name, task_id):
        return self.get("/dedicated/server/{}/task/{}"
                        .format(server_name, task_id))

    def get_ipxescript_boot_id(self, server_name, script_name):
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
            LOG.debug("YANN Get ipxeCustomerScript for {}. Result={}"
                      .format(server_name, result))
        except requests.exceptions.HTTPError as e:
            LOG.error("Could not retrieve boot scripts for server %(server)s: "
                      "%(error)s",
                      {'server': server_name, 'error': e})
            raise e

        for boot_id in result:
            try:
                result = self.get(
                    "/dedicated/server/{}/boot/{}"
                    .format(server_name, boot_id)).json()
                LOG.debug("YANN Get boot info for {}. Result={}"
                          .format(server_name, result))
            except requests.exceptions.HTTPError as e:
                LOG.warning("Could not get the description of bootId {} for "
                            "server '{}'. Skipping. Exception: {}"
                            .format(boot_id, server_name, e))
                continue

            # If this bootId corresponds to the script we are looking for,
            # return it
            if result.get("kernel", "") == script_name:
                LOG.debug("YANN boot_id found {}: {} -> {}"
                          .format(server_name, script_name, boot_id))
                return boot_id

        # TODO(pgaxatte): use a real custom exception
        e = Exception("No script {} found for server {}"
                      .format(script_name, server_name))
        LOG.error("Could not retrieve the ID of the script %(script)s: %(error)s",
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
            LOG.debug("YANN Get harddisk boot id for {}. Result={}"
                      .format(server_name, result))
        except requests.exceptions.HTTPError as e:
            LOG.error("Could not retrieve boot script for server %(server)s: "
                      "%(error)s",
                      {'server': server_name, 'error': e})
            raise e

        for boot_id in result:
            LOG.debug("YANN return first harddisk boot id found for {}. Result={}"
                      .format(server_name, boot_id))
            return boot_id

        e = Exception("No id for boot type harddisk found for server {}"
                      .format(script_name))
        raise e
