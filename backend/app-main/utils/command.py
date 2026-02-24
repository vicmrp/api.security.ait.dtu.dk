from myview.models import ADStaffSyncGroup



class Command:

    def sync_ad_groups(self, *args, **options):
        from myview.models import ADStaffSyncGroup
        ADStaffSyncGroup.sync_ad_groups(None)
        print('done')
        return True



def run():
    command = Command()
    command.sync_ad_groups()
    print('done')

# if main 
if __name__ == "__main__":
    run()

