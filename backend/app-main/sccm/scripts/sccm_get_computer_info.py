import pyodbc
import os
import json

# Load .env file
# Import load_dotenv
from dotenv import load_dotenv
load_dotenv()


def get_computer_info(computer_name):
    # load env variables SCCM_USERNAME and SCCM_PASSWORD
    sccm_username = os.getenv("SCCM_USERNAME")
    sccm_password = os.getenv("SCCM_PASSWORD")


    final_dict = {
        "v_r_system": {},
        "v_add_remove_programs": [],
        "v_gs_computer_system": [],

    }
    row_dict = {}

    # Connection string
    connection_string = (
        r'DRIVER=/opt/microsoft/msodbcsql18/lib64/libmsodbcsql-18.3.so.2.1;'
        'SERVER=ait-pcmdb01.win.dtu.dk,1433;'
        'TrustServerCertificate=yes;'
        f'UID={sccm_username};'
        f'PWD={sccm_password}'
    )

    # Connect to the SCCM database
    try:
        sccmdbh = pyodbc.connect(connection_string)
    except pyodbc.Error as e:
        print(f"Error connecting to the SCCM database: {e}")
        exit()

    # Execute the USE statement
    try:
        sccmdbh.execute("USE CM_P01")
    except pyodbc.Error as e:
        print(f"Error executing USE statement: {e}")
        return None, f"Internal server error"        


    # Find the resourceID of the computer
    try:
        sql = "SELECT ResourceID FROM v_R_System WHERE Netbios_Name0=?"
        cursor = sccmdbh.execute(sql, computer_name)
        row = cursor.fetchone()
        if row is None:
            return None, f"No computer found with name {computer_name}"
        resource_id = row[0]
    except pyodbc.Error as e:
        print(f"Error: executing SQL statement: {e}")
        return None, f"Internal server error"
    







    sql_statement_1 = """
SELECT  DISTINCT TOP 1
SYS.ResourceID,
SYS.Name0 DeviceName, 
SYS.AD_Site_Name0 ADSite, 
USR.Full_User_Name0 FullUserName,
SYS.User_Name0 as 'LastLogonUser',
CASE CHCS.ClientActiveStatus WHEN '1' THEN 'Active' WHEN '0' THEN 'Inactive' END AS 'Client Active Status', 
CASE SYS.Client0 WHEN '1' THEN 'Yes' WHEN '0' THEN 'No' ELSE 'Unknown' END AS 'SCCM Client Installed',
CS.Manufacturer0 Manufacturer,
CS.Model0 Model, 
CASE WHEN OS.Caption0 LIKE '% 10 En%' OR OS.Caption0 = 'Microsoft Windows 10 Entreprise' THEN 'Microsoft Windows 10 Enterprise' 
WHEN OS.Caption0 LIKE '\%s 10 Pro%' THEN 'Microsoft Windows 10 Pro' 
WHEN OS.Caption0 = 'Microsoft Windows 7 Professionnel' THEN 'Microsoft Windows 7 Professional' WHEN OS.Caption0 = 'Microsoft Windows 7 Entreprise' THEN 'Microsoft Windows 7 Enterprise'
WHEN OS.Caption0 = 'Microsoft Windows 10 Professionnel' THEN 'Microsoft Windows 10 Pro' ELSE OS.Caption0 END OSName,
OS.Version0 OSVersion,
EV.DriveLetter0 DriverLetter,
SE.ChassisTypes0 as 'ComputerType',
Last_Logon_Timestamp0 as 'LastLogon',
Operating_System_Name_and0 as 'OperatingSystem', 
LDisk.Size0 as 'SystemDriveSize', 
LDisk.FreeSpace0 AS 'SystemDriveFree', 
UniqueUserName as 'PrimaryUser',
CASE EV.ProtectionStatus0 WHEN '0' THEN 'Off' WHEN '1' THEN 'On' WHEN '2' THEN 'No Data' END AS 'Bitlocker Enabled',
CASE EV.ProtectionStatus0 WHEN '0' THEN 0 WHEN '1' THEN 1 WHEN '2' THEN NULL END AS 'SystemDriveEncryption',
CASE WHEN (TPM.IsActivated_InitialValue0 = 1) then 'Yes' else 'No' END [TPM Activated],  
CASE WHEN (TPM.IsEnabled_InitialValue0 = 1) then 'Yes' else 'No' END [TPM Enabled],  
CASE WHEN (TPM.IsOwned_InitialValue0 = 1) then 'Yes' else 'No' END [TPM Owned], 
TPM.PhysicalPresenceVersionInfo0 PhysicalPresenceVersionInfo,
ComplianceStatus = CASE WHEN BD.Compliant0 = 1 THEN 'Compliant' WHEN BD.Compliant0 = 0 THEN 'NonCompliant' ELSE 'Unknown' END,
ConversionStatus = CASE WHEN BD.ConversionStatus0 = 1 THEN 'Converted' WHEN BD.ConversionStatus0 = 0 THEN 'NotConverted' ELSE 'Unknown' END,
EncryptionMethod = CASE WHEN (BD.EncryptionMethod0 = 0) THEN 'Not Encrypted'
		   WHEN (BD.EncryptionMethod0 = 1) THEN 'AES 128 With Diffuser'
		   WHEN (BD.EncryptionMethod0 = 2) THEN 'AES 256 With Diffuser'
		   WHEN (BD.EncryptionMethod0 = 3) THEN 'AES 128'
		   WHEN (BD.EncryptionMethod0 = 4) THEN 'AES 256'
		   WHEN (BD.EncryptionMethod0 = 5) THEN 'Hardware Encryption'
		   WHEN (BD.EncryptionMethod0 = 6) THEN 'XTS AES 128'
		   WHEN (BD.EncryptionMethod0 = 7) THEN 'XTS AES 256'
           WHEN (BD.EncryptionMethod0 > 1) THEN 'Unknown Algorithm/Partial Encryption'
		   WHEN (BD.EncryptionMethod0 is NULL) THEN 'Unknown'
		END,
AutoUnLockStatus =
		CASE 
			WHEN BD.IsAutoUnlockEnabled0 = 1 THEN 'Enabled'
			WHEN BD.IsAutoUnlockEnabled0 = 0 THEN 'Disabled'
			ELSE 'Unknown'
		END,
VolumeType = 
		CASE
		   WHEN (BD.MbamVolumeType0 = 0) THEN 'OSVolume'
		   WHEN (BD.MbamVolumeType0 = 1) THEN 'OSVolume'
		   WHEN (BD.MbamVolumeType0 = 2) THEN 'FixedVolume'
		   WHEN (BD.MbamVolumeType0 = 3) THEN 'RemovableVolume'
		   WHEN (BD.MbamVolumeType0 = 4) THEN 'OtherVolume'
		   ELSE 'Unknown'
		END,
ProtectionStatus = 
		CASE 
			WHEN BD.ProtectionStatus0 = 0 THEN 'Off'
			WHEN BD.ProtectionStatus0 = 1 THEN 'On'
			WHEN BD.ProtectionStatus0 = 2 THEN 'Unknown'
			ELSE 'Unknown' 
		END,
ReasonsForNonCompliance = ReasonsForNonCompliance0,
WS.LastHWScan
FROM V_R_SYStem SYS  
JOIN dbo.v_FullCollectionMembership FCM ON FCM.ResourceID = SYS.ResourceID AND FCM.CollectionID = 'P0102699'
LEFT JOIN v_gs_operating_system OS on SYS.ResourceID = OS.ResourceID
LEFT JOIN v_r_user USR on USR.User_Name0 = SYS.User_Name0
INNER JOIN v_GS_ENCRYPTABLE_VOLUME EV ON SYS.ResourceID = EV.ResourceID
INNER JOIN v_GS_SYSTEM_ENCLOSURE SE ON EV.ResourceID = SE.ResourceID 
INNER JOIN v_GS_COMPUTER_SYSTEM CS ON SE.ResourceID = CS.ResourceID
INNER JOIN v_GS_Logical_Disk LDisk on LDisk.ResourceID = SYS.ResourceID 
LEFT OUTER JOIN v_CH_ClientSummary CHCS ON SE.ResourceID = CHCS.ResourceID 
LEFT OUTER JOIN v_GS_WORKSTATION_STATUS WS ON CHCS.ResourceID = WS.ResourceID
LEFT JOIN v_GS_TPM TPM ON EV.ResourceID = TPM.ResourceID 
LEFT JOIN v_GS_BITLOCKER_DETAILS BD ON BD.ResourceID = FCM.ResourceID AND BD.DriveLetter0 = 'C:'
LEFT join v_UserMachineRelationship VUMR on SYS.ResourceID=VUMR.MachineResourceID 
WHERE EV.DriveLetter0 = 'C:' AND SYS.Name0 LIKE ('%' + ? + '%')
AND OS.Caption0 NOT LIKE '\%Server%'
ORDER BY SYS.Name0
"""

    # Execute the SQL statement1
    try:

        
        cursor = sccmdbh.execute(sql_statement_1, resource_id)
        row = cursor.fetchone()
        
        columns = [column[0] for column in cursor.description]

        # Check if the row is None and return an appropriate error message
        if row is None:
            return None, f"No computer found with name {resource_id}"


    except pyodbc.Error as e:
        print(f"Error: executing SQL statement: {e}")
        return None, f"Internal server error"

    row_dict = dict(zip(columns, row))
    final_dict["v_r_system"] = row_dict
    




    



































    sql_statement_2 = """

    -- v_Add_Remove_Programs: This view contains information about software that has been discovered from the "Add or Remove Programs" data on a client computer.
    SELECT
        ARP.ResourceID,
        ARP.GroupID,
        ARP.RevisionID,
        ARP.AgentID,
        ARP.TimeStamp,
        ARP.ProdID0,
        ARP.DisplayName0,
        ARP.InstallDate0,
        ARP.Publisher0,
        ARP.Version0

    FROM 
        V_R_System VRS 
        LEFT JOIN v_Add_Remove_Programs AS ARP ON ARP.ResourceID=VRS.ResourceID
        

    WHERE
        VRS.ResourceID=?



    """


    # Execute the SQL statement2
    try:

        cursor2 = sccmdbh.execute(sql_statement_2, resource_id)
        
        
        columns2 = [column[0] for column in cursor2.description]

        rows2 = cursor2.fetchall()

        # Check if the row is None and return an appropriate error message
        if rows2 is None:
            return None, f"No computer found with resource_id {resource_id}"
        
        # Convert each row to dictionary and append to the list
        for row2 in rows2:
            row_dict2 = dict(zip(columns2, row2))
            final_dict["v_add_remove_programs"].append(row_dict2)


        

    
    except pyodbc.Error as e:
        print(f"Error: executing SQL statement: {e}")
        return None, f"Internal server error"









































































    sql_statement_3 = """

    -- v_GS_INSTALLED_SOFTWARE: This view provides details about installed software discovered by the hardware inventory client agent.

SELECT
GIS.ResourceID,
GIS.GroupID,
GIS.RevisionID,
GIS.AgentID,
GIS.TimeStamp,
GIS.ARPDisplayName0,
GIS.ChannelCode0,
GIS.ChannelID0,
GIS.CM_DSLID0,
GIS.EvidenceSource0,
GIS.InstallDate0,
GIS.InstallDirectoryValidation0,
GIS.InstalledLocation0,
GIS.InstallSource0,
GIS.InstallType0,
GIS.LocalPackage0,
GIS.MPC0,
GIS.OsComponent0,
GIS.PackageCode0,
GIS.ProductID0,
GIS.ProductName0,
GIS.ProductVersion0,
GIS.Publisher0,
GIS.RegisteredUser0,
GIS.Publisher0,
GIS.RegisteredUser0,
GIS.ServicePack0,
GIS.SoftwareCode0,
GIS.SoftwarePropertiesHash0,
GIS.UninstallString0,
GIS.UpgradeCode0,
GIS.VersionMajor0,
GIS.VersionMinor0
FROM 
V_R_System VRS 
LEFT JOIN v_GS_INSTALLED_SOFTWARE AS GIS ON GIS.ResourceID=VRS.ResourceID
WHERE 
	VRS.ResourceID=?
    """


    # Execute the SQL statement3
    try:

        cursor3 = sccmdbh.execute(sql_statement_3, resource_id)
        
        
        columns3 = [column[0] for column in cursor3.description]

        rows3 = cursor3.fetchall()

        # Check if the row is None and return an appropriate error message
        if rows3 is None:
            return None, f"No computer found with resource_id {resource_id}"
        
        # Convert each row to dictionary and append to the list
        for row3 in rows3:
            row_dict3 = dict(zip(columns3, row3))
            final_dict["v_gs_computer_system"].append(row_dict3)


        

    
    except pyodbc.Error as e:
        print(f"Error: executing SQL statement: {e}")
        return None, f"Internal server error"



























































    return final_dict, None








































































def run():
    computer_info, message = get_computer_info("DTU-CND1363SBJ")
    if message:
        print(message)
    else:
        print(computer_info)




# if main 
if __name__ == "__main__":
    run()
