import sys
config_data = {}

def read():
    global config_data
    config_data = [i.strip().split(maxsplit=1) for i in open('config.txt').readlines() if i.strip()]
    config_data = dict(config_data)

def get(param):
    if param not in config_data:
        import log
        log.fatal('param {} not found'.format(param))
        sys.exit(0)
    try:
        return int(config_data[param])
    except ValueError:
        return config_data[param]

read()
