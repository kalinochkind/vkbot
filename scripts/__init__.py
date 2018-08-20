import importlib

import log


def runScript(name, args, api):
    log.local.script_name = name
    script = importlib.import_module('scripts.' + name)
    script.main(api, args)
