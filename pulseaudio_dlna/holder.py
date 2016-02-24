#!/usr/bin/python

# This file is part of pulseaudio-dlna.

# pulseaudio-dlna is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# pulseaudio-dlna is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with pulseaudio-dlna.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import logging
import threading

logger = logging.getLogger('pulseaudio_dlna.renderers')


class Holder(object):
    def __init__(
            self, plugins,
            stream_ip=None, stream_port=None, message_queue=None,
            device_filter=None, device_config=None):
        self.plugins = plugins
        self.stream_ip = stream_ip
        self.stream_port = stream_port
        self.device_filter = device_filter or []
        self.device_config = device_config or {}
        self.message_queue = message_queue
        self.devices = {}
        self.lock = threading.Lock()

    def search(self, ttl=None):
        threads = []
        for plugin in self.plugins:
            thread = threading.Thread(
                target=plugin.discover, args=[self, ttl])
            thread.daemon = True
            threads.append(thread)
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        logger.info('Holder.search() quit')

    def lookup(self, locations):
        for plugin in self.plugins:
            for device in plugin.lookup(locations):
                self.add_device(device)

    def add_device(self, device):
        if not device:
            return
        try:
            self.lock.acquire()
            if device.udn not in self.devices and device.validate():
                config = self.device_config.get(device.udn, None)
                device.activate(config)
                if self.stream_ip and self.stream_port:
                    device.set_server_location(
                        self.stream_ip, self.stream_port)
                if device.name not in self.device_filter:
                    if config:
                        logger.info(
                            'Using device configuration:\n{}'.format(
                                device.__str__(True)))
                    self.devices[device.udn] = device
                    if self.message_queue:
                        self.message_queue.put({
                            'type': 'add_device',
                            'device': device
                        })
                else:
                    logger.info('Skipped the device "{name}" ...'.format(
                        name=device.label))
        finally:
            self.lock.release()

    def remove_device(self, device_id):
        if not device_id or device_id not in self.devices:
            return
        try:
            self.lock.acquire()
            device = self.devices[device_id]
            if self.message_queue:
                self.message_queue.put({
                    'type': 'remove_device',
                    'device': device
                })
            del self.devices[device_id]
        finally:
            self.lock.release()
