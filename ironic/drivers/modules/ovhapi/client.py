# Authors: Raphael Glon, Sylvain Burette @ OVH SA.

import hashlib
import json
import re
import requests
import time

from oslo_log import log

from ironic.conf import CONF
from ironic.drivers.modules.ovhapi import ovh_base


OBFUSCATE_REGEX = re.compile('X-Ovh-Application|password|Signature|X-Ovh-Consumer', flags=re.IGNORECASE)

LOG = log.getLogger(__file__)

#: Mapping between OVH API region names and corresponding endpoints
ENDPOINTS = {
    'ovh-eu': 'https://eu.api.ovh.com/1.0',
    'ovh-us': 'https://api.us.ovhcloud.com/1.0',
    'ovh-ca': 'https://ca.api.ovh.com/1.0',
    'kimsufi-eu': 'https://eu.api.kimsufi.com/1.0',
    'kimsufi-ca': 'https://ca.api.kimsufi.com/1.0',
    'soyoustart-eu': 'https://eu.api.soyoustart.com/1.0',
    'soyoustart-ca': 'https://ca.api.soyoustart.com/1.0',
}

class BaseClient(ovh_base.Api):

    def __init__(self):
        # Try to use only one session
        # This prevents from starting a new connection each time
        # a call to get is made!
        self.s = requests.Session()
        debug = CONF.debug
        if debug:
            self.debug = 1
        else:
            self.debug = 0

        super(BaseClient, self).__init__(ENDPOINTS[CONF.ovhapi.endpoint], CONF.ovhapi.application_key,
                                         CONF.ovhapi.application_secret, CONF.ovhapi.consumer_key)

    # Super method + log in the middle
    def raw_call(self, method, path, content=None):
        """
        This is the main method of this wrapper. It will sign a given query and return its result.
        Arguments:
        - method: the HTTP method of the request (get/post/put/delete)
        - path: the url you want to request
        - content: the object you want to send in your request (will be automatically serialized to JSON)
        """
        target_url = self.base_url + path
        now = str(int(time.time()) + self.time_delta())
        body = ""
        if content is not None:
            body = json.dumps(content)
        s1 = hashlib.sha1()
        s1.update("+".join([self.application_secret, self.consumer_key, method.upper(), target_url, body, now]).encode('utf-8'))
        sig = "$1$" + s1.hexdigest()
        query_headers = {"X-Ovh-Application": self.application_key, "X-Ovh-Timestamp": now,
                         "X-Ovh-Consumer": self.consumer_key, "X-Ovh-Signature": sig,
                         "Content-type": "application/json"}
        if self.consumer_key == "":
            query_headers = {"X-Ovh-Application": self.application_key, "X-Ovh-Timestamp": now,
                             "Content-type": "application/json"}

        # Use the session init at startup
        req = getattr(self.s, method.lower())

        self.log_req(method.upper(), target_url, query_headers, body)

        return req(target_url, stream=False, headers=query_headers, data=body)

    def log_req(self, method, target_url, headers, data):
        if not self.debug:
            return

        string_parts = [
            "curl -g -i",
            "-X '%s'" % method,
            "'%s'" % target_url,
        ]

        for k, v in headers.iteritems():
            if OBFUSCATE_REGEX.search(k):
                v = 'OBFUSCATED'
            header = "-H '%s: %s'" % (k, v)
            string_parts.append(header)

        LOG.debug("REQ: %s" % " ".join(string_parts))
        if data:
            LOG.debug("REQ BODY: %s\n" % data)

    def list_servers(self):
        return self.get('/dedicated/server')

    def reboot_server(self, serverName):
        return self.post('/dedicated/server/%s/reboot' % serverName)

    def set_bootId(self, serverName, bootId):
        return self.put("/dedicated/server/%s" % serverName, bootId = bootId)

    def get_task(self, serverName, taskId):
        return self.get('/dedicated/server/%s/task/%s' % (serverName, taskId) )

    def post(self, path, **kwargs):
        return super(BaseClient, self).post(path, content=kwargs)

    def put(self, path, **kwargs):
        return super(BaseClient, self).put(path, content=kwargs)

    def get(self, path, **kwargs):
        return super(BaseClient, self).get(path, content=kwargs)
