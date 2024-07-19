# SPDX-License-Identifier: BSD-3-Clause
#
# Copyright 2020 Raritan Inc. All rights reserved.
#
# This is an auto-generated file.

#
# Section generated by IdlC from "RawConfiguration.idl"
#

import raritan.rpc
from raritan.rpc import Interface, Structure, ValueObject, Enumeration, typecheck, DecodeException
import raritan.rpc.rawcfg


# interface
class RawConfiguration(Interface):
    idlType = "rawcfg.RawConfiguration:1.0.0"

    # enumeration
    class Status(Enumeration):
        idlType = "rawcfg.RawConfiguration.Status:1.0.0"
        values = ["UNKNOWN", "UPLOAD_FAILED", "UPDATE_PENDING", "UPDATE_OK", "UPDATE_FAILED"]

    Status.UNKNOWN = Status(0)
    Status.UPLOAD_FAILED = Status(1)
    Status.UPDATE_PENDING = Status(2)
    Status.UPDATE_OK = Status(3)
    Status.UPDATE_FAILED = Status(4)

    class _getStatus(Interface.Method):
        name = 'getStatus'

        @staticmethod
        def encode():
            args = {}
            return args

        @staticmethod
        def decode(rsp, agent):
            status = raritan.rpc.rawcfg.RawConfiguration.Status.decode(rsp['status'])
            timeStamp = raritan.rpc.Time.decode(rsp['timeStamp'])
            typecheck.is_enum(status, raritan.rpc.rawcfg.RawConfiguration.Status, DecodeException)
            typecheck.is_time(timeStamp, DecodeException)
            return (status, timeStamp)
    def __init__(self, target, agent):
        super(RawConfiguration, self).__init__(target, agent)
        self.getStatus = RawConfiguration._getStatus(self)

# from raritan/rpc/rawcfg/__extend__.py
def upload(agent, data):
    """
    Method to upload raw config files

    **parameters**, **return**

    :param agent: An agent instance for the device where the config should be uploaded
    :param data: The binary data of the raw config file
    :return: return upload response

    **Example**
        :Example:

        from raritan import rpc
        from raritan.rpc import rawcfg

        agent = rpc.Agent("https", "my-pdu.example.com", "admin", "raritan")

        # read file in binary mode
        cfgFile = open("config.txt", "rb")
        # upload
        code = rawcfg.upload(agent, cfgFile.read())
        # view code
        print(code)

    """
    target = "cgi-bin/raw_config_update.cgi"
    response = agent.form_data_file(target, [data], ["config.txt"], ["config_file"], ["application/octet-stream"])
    return response.headers.get("X-Response-Code")

def download_rawcfg(agent):
    """
    Method to download the configuration data

    **parameters**

    :param agent: An agent instance from the device where the raw configuration data should be downloaded
    :return: returns the raw configuration data

    **Example**
        :Example:

        from raritan import rpc
        from raritan.rpc import rawcfg

        agent = rpc.Agent("https", "my-pdu.example.com", "admin", "raritan")
        # download
        raw_cfg = rawcfg.download_rawcfg(agent)
        print(raw_cfg)
    """
    target = "cgi-bin/raw_config_download.cgi"
    return agent.get(target)