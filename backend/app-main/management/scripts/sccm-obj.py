import pyodbc
import os
import json

# Load .env file
# Import load_dotenv
from dotenv import load_dotenv
load_dotenv()

def run():
    # load env variables SCCM_USERNAME and SCCM_PASSWORD
    sccm_username = os.getenv("SCCM_USERNAME")
    sccm_password = os.getenv("SCCM_PASSWORD")

    # Connection string
    connection_string = (
        r'DRIVER=/opt/microsoft/msodbcsql18/lib64/libmsodbcsql-18.3.so.1.1;'
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
    sccmdbh.execute("USE CM_P01")


    sql_statement = """
-- TOP 1 is used to limit the result to 1 row
SELECT DISTINCT TOP 1
    VRS.Netbios_Name0 as 'MachineName', 
    VCS.Model0 as 'Model', 
    VCS.ResourceID,  
    VRS.description0 as 'Description',  
    VENCVOL.DriveLetter0 as 'SystemDrive', 
    VENCVOL.ProtectionStatus0 as 'SystemDriveEncryption', 
    VENCL.ChassisTypes0 as 'ComputerType',
    VRS.Last_Logon_Timestamp0 as 'LastLogon',
    VRS.CPUType0 as 'CPUType',
    VRS.Operating_System_Name_and0 as 'OperatingSystem', 
    LDisk.Size0 as 'SystemDriveSize', 
    LDisk.FreeSpace0 AS 'SystemDriveFree', 
    VUMR.UniqueUserName as 'PrimaryUser', 
    VRS.User_Name0 as 'LastLogonUser',

    -- sccm agent status
    ws.LastHWScan, 

    -- last boot time
    OS.LastBootUpTime0 AS 'LastBootTime',

    -- TPM
    v_GS_TPM.SpecVersion0 as 'TPMVersion',
    v_GS_TPM.IsActivated_InitialValue0 as 'TPMActivated',
    v_GS_TPM.IsEnabled_InitialValue0 as 'TPMEnabled',
    v_GS_TPM.IsOwned_InitialValue0 as 'TPMOwned',

    -- uefi
    SecureBoot0 AS 'SecureBoot',
    UEFI0 AS 'UEFI',

    VRS.Build01 as 'OSVesionBuild'

FROM (
    V_R_System VRS 
    INNER JOIN v_GS_COMPUTER_SYSTEM VCS on VCS.ResourceID=VRS.ResourceID 
    INNER JOIN v_GS_Logical_Disk LDisk on LDisk.ResourceID = VRS.ResourceID 
    INNER JOIN v_GS_WORKSTATION_STATUS as ws ON VRS.ResourceID = ws.ResourceID 
    INNER JOIN v_GS_TPM ON VRS.ResourceID = v_GS_TPM.ResourceID
    INNER JOIN v_GS_FIRMWARE AS fw ON VRS.ResourceID = fw.ResourceID
    INNER JOIN v_GS_OPERATING_SYSTEM OS ON OS.ResourceID = VRS.ResourceID
    LEFT JOIN v_GS_ENCRYPTABLE_VOLUME VENCVOL ON VENCVOL.ResourceID = VRS.ResourceID 
    LEFT JOIN v_GS_SYSTEM_ENCLOSURE VENCL on VENCL.ResourceID = VRS.ResourceID
    LEFT JOIN v_UserMachineRelationship VUMR on VRS.ResourceID=VUMR.MachineResourceID 
  ) 
WHERE
    VRS.Netbios_Name0=?
"""

    # Execute the SQL statement
    try:
        cursor = sccmdbh.execute(sql_statement, "DTU-CND1363SBJ")
        row = cursor.fetchone()
        
        columns = [column[0] for column in cursor.description]


        # Convert the row to a dictionary
        row_dict = dict(zip(columns, row))

        # Convert the dictionary to a JSON string
        row_json = json.dumps(row_dict, default=str) # Use default=str to handle the datetime object

        print(row_json)
        # convert to json
        # convert row to type so it can be serialized by
            # convert to json

            # convert row to type so it can be serialized by 

    except pyodbc.Error as e:
        print(f"Error executing SQL statement: {e}")
        exit()

# if main 
if __name__ == "__main__":
    run()
