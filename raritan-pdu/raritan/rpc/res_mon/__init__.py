# SPDX-License-Identifier: BSD-3-Clause
#
# Copyright 2020 Raritan Inc. All rights reserved.
#
# This is an auto-generated file.

#
# Section generated by IdlC from "ResMon.idl"
#

import raritan.rpc
from raritan.rpc import Interface, Structure, ValueObject, Enumeration, typecheck, DecodeException
import raritan.rpc.res_mon


# structure
class Entry(Structure):
    idlType = "res_mon.Entry:1.0.0"
    elements = ["type", "name", "value"]

    def __init__(self, type, name, value):
        typecheck.is_enum(type, raritan.rpc.res_mon.Entry.Type, AssertionError)
        typecheck.is_string(name, AssertionError)
        typecheck.is_long(value, AssertionError)

        self.type = type
        self.name = name
        self.value = value

    @classmethod
    def decode(cls, json, agent):
        obj = cls(
            type = raritan.rpc.res_mon.Entry.Type.decode(json['type']),
            name = json['name'],
            value = int(json['value']),
        )
        return obj

    def encode(self):
        json = {}
        json['type'] = raritan.rpc.res_mon.Entry.Type.encode(self.type)
        json['name'] = self.name
        json['value'] = self.value
        return json

    # enumeration
    class Type(Enumeration):
        idlType = "res_mon.Entry.Type:1.0.0"
        values = ["GLOBAL_CPU_USAGE", "GLOBAL_FREE_MEM", "GLOBAL_PROC_COUNT", "FS_FREE_SPACE", "FS_FREE_INODES", "PROC_CPU_USAGE", "PROC_VM_SIZE", "PROC_FREE_FILE_DESC", "PROC_LIFE_TIME", "PROC_COUNT"]

    Type.GLOBAL_CPU_USAGE = Type(0)
    Type.GLOBAL_FREE_MEM = Type(1)
    Type.GLOBAL_PROC_COUNT = Type(2)
    Type.FS_FREE_SPACE = Type(3)
    Type.FS_FREE_INODES = Type(4)
    Type.PROC_CPU_USAGE = Type(5)
    Type.PROC_VM_SIZE = Type(6)
    Type.PROC_FREE_FILE_DESC = Type(7)
    Type.PROC_LIFE_TIME = Type(8)
    Type.PROC_COUNT = Type(9)

# interface
class ResMon(Interface):
    idlType = "res_mon.ResMon:1.0.0"

    class _getDataEntries(Interface.Method):
        name = 'getDataEntries'

        @staticmethod
        def encode():
            args = {}
            return args

        @staticmethod
        def decode(rsp, agent):
            entries = [raritan.rpc.res_mon.Entry.decode(x0, agent) for x0 in rsp['entries']]
            for x0 in entries:
                typecheck.is_struct(x0, raritan.rpc.res_mon.Entry, DecodeException)
            return entries
    def __init__(self, target, agent):
        super(ResMon, self).__init__(target, agent)
        self.getDataEntries = ResMon._getDataEntries(self)
