from rest_framework import serializers
from .models import Item

class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ['id', 'name', 'description']





class VRSystemSerializer(serializers.Serializer):
    Netbios_Name0 = serializers.CharField()
    Last_Logon_Timestamp0 = serializers.DateTimeField()
    CPUType0 = serializers.CharField()
    Operating_System_Name_and0 = serializers.CharField()
    Build01 = serializers.CharField()
    User_Name0 = serializers.CharField()
    description0 = serializers.CharField(required=False, allow_null=True)
    Model0 = serializers.CharField()
    ResourceID = serializers.IntegerField()
    Size0 = serializers.IntegerField()
    FreeSpace0 = serializers.IntegerField()
    LastHWScan = serializers.DateTimeField()
    SpecVersion0 = serializers.CharField()
    IsActivated_InitialValue0 = serializers.BooleanField() 
    IsEnabled_InitialValue0 = serializers.BooleanField()
    IsOwned_InitialValue0 = serializers.BooleanField()
    SecureBoot0 = serializers.BooleanField()
    UEFI0 = serializers.BooleanField()
    LastBootUpTime0 = serializers.DateTimeField()
    DriveLetter0 = serializers.CharField()
    ProtectionStatus0 = serializers.BooleanField()
    ChassisTypes0 = serializers.CharField()
    UniqueUserName = serializers.CharField()



class AddRemoveProgramsSerializer(serializers.Serializer):
    ResourceID = serializers.IntegerField()
    GroupID = serializers.IntegerField()
    RevisionID = serializers.IntegerField()
    AgentID = serializers.IntegerField()
    TimeStamp = serializers.DateTimeField()
    ProdID0 = serializers.CharField()
    DisplayName0 = serializers.CharField()
    InstallDate0 = serializers.DateField(allow_null=True)
    Publisher0 = serializers.CharField()
    Version0 = serializers.CharField()


class GSComputerSystemSerializer(serializers.Serializer):
    ResourceID = serializers.IntegerField()
    GroupID = serializers.IntegerField()
    RevisionID = serializers.IntegerField()
    AgentID = serializers.IntegerField()
    TimeStamp = serializers.DateTimeField()
    ARPDisplayName0 = serializers.CharField()
    ChannelCode0 = serializers.CharField(allow_blank=True)
    ChannelID0 = serializers.CharField(allow_blank=True)
    CM_DSLID0 = serializers.CharField(allow_blank=True)
    EvidenceSource0 = serializers.CharField(allow_blank=True)
    InstallDate0 = serializers.DateTimeField()
    InstallDirectoryValidation0 = serializers.IntegerField()
    InstalledLocation0 = serializers.CharField(allow_blank=True)
    InstallSource0 = serializers.CharField()
    InstallType0 = serializers.IntegerField()
    LocalPackage0 = serializers.CharField()
    MPC0 = serializers.CharField(allow_blank=True)
    OsComponent0 = serializers.IntegerField()
    PackageCode0 = serializers.CharField()
    ProductID0 = serializers.CharField(allow_blank=True)
    ProductName0 = serializers.CharField()
    ProductVersion0 = serializers.CharField()
    Publisher0 = serializers.CharField()
    RegisteredUser0 = serializers.CharField(allow_blank=True)
    ServicePack0 = serializers.CharField(allow_blank=True)
    SoftwareCode0 = serializers.CharField()
    SoftwarePropertiesHash0 = serializers.CharField()
    UninstallString0 = serializers.CharField()
    UpgradeCode0 = serializers.CharField(allow_blank=True)
    VersionMajor0 = serializers.IntegerField()
    VersionMinor0 = serializers.IntegerField()

class ComputerInfoSerializer(serializers.Serializer):
    v_r_system = VRSystemSerializer(many=False)
    v_gs_computer_system = GSComputerSystemSerializer(many=True)
    v_add_remove_programs = AddRemoveProgramsSerializer(many=True)


