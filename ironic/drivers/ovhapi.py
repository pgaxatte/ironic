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

"""
OVH API hardware types.
"""

from ironic.drivers import generic
from ironic.drivers.modules import inspector
from ironic.drivers.modules import noop
from ironic.drivers.modules.ovhapi import management
from ironic.drivers.modules.ovhapi import power


class OvhApiHardware(generic.GenericHardware):
    """OVH API Hardware type """

    @property
    def supported_management_interfaces(self):
        """List of supported management interfaces."""
        return [management.OvhApiManagement]

    @property
    def supported_power_interfaces(self):
        """List of supported power interfaces."""
        return [power.OvhApiPower]

    @property
    def supported_inspect_interfaces(self):
        """List of supported inspect interfaces."""
        return [inspector.Inspector, noop.NoInspect]
