from ping3 import ping, verbose_ping





def ping_host(host):
    try:
        result = ping(host)  # Returns delay in seconds.
        if result is not None:
            print('Connection successful')
        else:
            print('No response')
    except Exception as e:
        print('Ping failed:', e)





def run():
    ping_host('beta-api-security-ait-dtu-dk-mariadb-service')