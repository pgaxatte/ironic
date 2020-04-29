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

from oslo_config import cfg

from ironic.common.i18n import _
from ironic.drivers.modules.ovhapi.ovh_base import ENDPOINTS

opts = [
    cfg.StrOpt('endpoint',
               default='ovh-eu',
               choices=ENDPOINTS.items(),
               help=_('Endpoint of the OVH API')),
    cfg.StrOpt('application_key',
               help=_('Application Key, see https://docs.ovh.com/gb/en/'
                      'customer/first-steps-with-ovh-api/')),
    cfg.StrOpt('consumer_key',
               help=_('Consumer Key, see https://docs.ovh.com/gb/en/customer'
                      '/first-steps-with-ovh-api/')),
    cfg.StrOpt('application_secret',
               help=_('Application secret, see https://docs.ovh.com/gb/en/'
                      'customer/first-steps-with-ovh-api/')),
    cfg.StrOpt('poweroff_script',
               help=_('Name of the poweroff script to use, see '
                      'https://api.ovh.com/console/#/me/ipxeScript#GET')),
    cfg.StrOpt('boot_script',
               help=_('Name of the boot script to use, see '
                      'https://api.ovh.com/console/#/me/ipxeScript#GET')),
]


def register_opts(conf):
    conf.register_opts(opts, group='ovhapi')
