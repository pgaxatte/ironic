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

import hashlib
import json
import re
import time

from oslo_log import log
import requests

LOG = log.getLogger(__file__)
# Regex to obfuscate log requests when debugging
OBFUSCATE_REGEX = re.compile(
    'X-Ovh-Application|password|Signature|X-Ovh-Consumer',
    flags=re.IGNORECASE
)

# Mapping between OVH API region names and corresponding endpoints
ENDPOINTS = {
    'ovh-eu': 'https://eu.api.ovh.com/1.0',
    'ovh-us': 'https://api.us.ovhcloud.com/1.0',
    'ovh-ca': 'https://ca.api.ovh.com/1.0',
    'kimsufi-eu': 'https://eu.api.kimsufi.com/1.0',
    'kimsufi-ca': 'https://ca.api.kimsufi.com/1.0',
    'soyoustart-eu': 'https://eu.api.soyoustart.com/1.0',
    'soyoustart-ca': 'https://ca.api.soyoustart.com/1.0',
}


class Api(object):

    def __init__(self, endpoint_url, application_key, application_secret,
                 consumer_key="", debug=False):
        """Initializes an OVH API client.

        :param endpoint_url: the OVH endpoint you want to call
        :param application_key: your application key given by OVH on
            application registration
        :param application_secret: your application secret given by OVH on
            application registration
        :param consumer_key: the consumer key you want to use, if any, given
            after a credential request
        :param debug: whether or not to log requests
        """
        self.endpoint_url = endpoint_url
        self.application_key = application_key
        self.application_secret = application_secret
        self.consumer_key = consumer_key
        self.debug = debug

        self.session = requests.Session()

        self._time_delta = None

    def time_delta(self):
        """Retrieves the API's time delta.

        Retrieves the time delta between this computer and the OVH cluster
        to sign further queries.

        :returns: the time delta in seconds.
        """
        if self._time_delta is None:
            result = self.session.get(self.endpoint_url + "/auth/time")
            result.raise_for_status()
            self._time_delta = int(result.text) - int(time.time())
        return self._time_delta

    def _call(self, method, path, content=None):
        """Calls the API with the given parameters.

        The request will be signed if the consumer key has been set.

        :param method: the HTTP method of the request (get/post/put/delete)
        :param path: the url you want to request
        :param content: the object you want to send in your request
            (will be automatically serialized to JSON)
        :raises: requests.exceptions.HTTPError if the API return an error
        """
        target_url = self.endpoint_url + path
        now = str(int(time.time()) + self.time_delta())
        body = ""
        if content is not None:
            body = json.dumps(content)

        headers = {
            "Content-type": "application/json",
            "X-Ovh-Application": self.application_key,
            "X-Ovh-Timestamp": now,
        }

        if self.consumer_key != "":
            # Compute the call signature for authentication
            s1 = hashlib.sha1()
            s1.update("+".join([
                self.application_secret,
                self.consumer_key,
                method.upper(),
                target_url,
                body,
                now
            ]).encode('utf-8'))
            headers["X-Ovh-Consumer"] = self.consumer_key
            headers["X-Ovh-Signature"] = "$1$" + s1.hexdigest()

        # Re-use the session init at startup
        req = getattr(self.session, method.lower())

        self._log_request(method.upper(), target_url, headers, body)

        try:
            result = req(target_url, stream=False, headers=headers, data=body)
            result.raise_for_status()
        except requests.exceptions.HTTPError as e:
            LOG.error("Error querying OVH API:", e)
            raise e
        return result

    def _log_request(self, method, target_url, headers, data):
        """Logs the request made for debugging purposes.

        :param method: the HTTP method of the request (get/post/put/delete)
        :param target_url: the url requested
        :param headers: the headers passed in the request
        :param data: the data passed in the request
        """
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
            header = "-H '{}: {}'".format(k, v)
            string_parts.append(header)

        LOG.debug("OVH API REQ: {}".format(" ".join(string_parts)))
        if data:
            LOG.debug("OVH API REQ BODY: {}".format(data))

    def get(self, path):
        """Wraps call to _call("get")

        :param path: the url of the resource you want to get
        """
        return self._call("get", path)

    def put(self, path, content):
        """Wraps a call to _call("put")

        :param path: the url of the resource you want to modify
        :param content: the object you want to modify
        """
        return self._call("put", path, content)

    def post(self, path, content):
        """Wraps a call to _call("post")

        :param path: the url of the resource you want to create
        :param content: the object you want to create
        """
        return self._call("post", path, content)

    def delete(self, path):
        """Wraps a call to _call("delete")

        :param path: the url of the resource you want to delete
        """
        return self._call("delete", path)
