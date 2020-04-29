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

from ironic.conf import CONF
from ironic.drivers.modules.ovhapi import ENDPOINTS
from ironic.drivers.modules.ovhapi import ovh_base

LOG = log.getLogger(__file__)


class BaseClient(ovh_base.Api):

    def __init__(self):
        super(BaseClient, self).__init__(
            ENDPOINTS.get(CONF.ovhapi.endpoint),
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
        return self.post("/dedicated/server/{}/reboot".format(server_name))

    def set_boot_script(self, server_name, script_name):
        """Sets the server to point on the specified boot script

        :param server_name: the name of the server to configure
        :param script_name: the name of the script to use on next boot
        """
        boot_id = self.get_ipxe_script_id(server_name, script_name)
        return self.put("/dedicated/server/{}"
                        .format(server_name), boot_id=boot_id)

    def get_task(self, server_name, task_id):
        return self.get("/dedicated/server/{}/task/{}"
                        .format(server_name, task_id))

    def get_ipxe_script_id(self, server_name, script_name):
        """Gets the ID of a ipxe script from its name for a given server.

        :raises: requests.exceptions.HTTPError if the API return an error
        :raises: Exception if not matching script is found
        :returns: the ID of the script
        """
        try:
            result = self.get("/dedicated/server/{}/boot".format(server_name))
        except requests.exceptions.HTTPError as e:
            LOG.error("Could not retrieve boot scripts for server '{}': {}"
                      .format(server_name, e))
            raise e

        for boot_id in result:
            try:
                result = self.get("/dedicated/server/{}/boot/{}"
                                  .format(server_name, boot_id))
            except requests.exceptions.HTTPError as e:
                LOG.warning("Could not get the description of bootId {} for "
                            "server '{}'. Skipping. Exception: {}"
                            .format(boot_id, server_name, e))
                continue

            # If this bootId corresponds to the script we are looking for,
            # return it
            if result.get("kernel", "") == script_name:
                return boot_id

        # TODO(pgaxatte): use a real custom exception
        e = Exception("No script {} found for server {}"
                      .format(script_name, server_name))
        LOG.error("Could not retrieve the ID of the script: {}".format(e))
        raise e
