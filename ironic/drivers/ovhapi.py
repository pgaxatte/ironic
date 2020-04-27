from ironic.drivers import generic
from ironic.drivers.modules import fake
from ironic.drivers.modules import noop_mgmt
from ironic.drivers.modules.ovhapi import power


class OvhApiHardware(generic.GenericHardware):

    @property
    def supported_management_interfaces(self):
        """List of supported management interfaces."""
        return [noop_mgmt.NoopManagement, fake.FakeManagement]

    @property
    def supported_power_interfaces(self):
        """List of supported power interfaces."""
        return [power.OvhApiPower]
