from ldap3 import ALL_ATTRIBUTES
from rest_framework import viewsets, status
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from drf_yasg import openapi
from .services import get_inactive_computers
from graph.views import APIAuthBaseViewSet
from rest_framework.decorators import action
from .services import execute_active_directory_query, execute_active_directory_query_assistant
import datetime
import base64



class ActiveDirectoryQueryAssistantViewSet(viewsets.ViewSet):
    authentication_classes = [TokenAuthentication]  # Require token authentication for this view
    permission_classes = [IsAuthenticated]  # Require authenticated user for this view

    header_parameter = openapi.Parameter(
        'Authorization',  # name of the header
        in_=openapi.IN_HEADER,  # where the parameter is located
        description="Type: Token \<token\>",
        type=openapi.TYPE_STRING,  # type of the parameter
        required=True,  # if the header is required or not
        default='<token>'  # default value
    )

    @swagger_auto_schema(
        manual_parameters=[header_parameter],
        operation_description="""
        Active Directory Query Assistant
        
        This assistant helps generate Active Directory query parameters based on user requests. It provides a structured JSON response with the necessary fields for querying the Active Directory. The 'explanation' field should contain a brief description of the query parameters generated.

        Curl example: \n
        \t curl --location --request POST 'http://api.security.ait.dtu.dk/active-directory/v1-0-0/query-assistant/' \
        \t --header 'Authorization:\<token\>' \
        \t --header 'Content-Type: application/json' \
        \t --data-raw '{
        \t     "user_prompt": "Retrieve all disabled user accounts in 'DTUBasen' and include their account names and statuses."
        \t }'
        
        """,
        responses={
            # 200: ComputerInfoSerializer(),
            400: 'Error: Computer name must be provided.',
            404: 'Error: No computer found with given name',
            500: 'Error: Internal server error'
        },

    )
    def create(self, request):
        user_prompt = request.data.get('user_prompt')

        response = execute_active_directory_query_assistant(user_prompt)
        return Response(response, status=status.HTTP_200_OK)






class ActiveDirectoryQueryViewSet(APIAuthBaseViewSet):

    @swagger_auto_schema(
        method='get',
        operation_description="""
**Active Directory Query Endpoint**

This endpoint allows querying Active Directory based on given criteria. It provides flexibility in specifying which attributes to return, applying filters, and pagination control.

The synergy between the parameters allows for tailored queries:

- **`base_dn`**: Specifies the starting point within the AD structure.
- **`search_filter`**: Narrows down the objects based on specified conditions.
- **`search_attributes`**: Controls which attributes of the objects are retrieved.
- **`limit`**: Provides pagination capability.
- **`excluded_attributes`**: Refines the returned data by excluding specified attributes, enhancing query efficiency and relevance.


### OU Structure

Below is the structure of the Organizational Units (OUs) in `win.dtu.dk`:

win.dtu.dk
|-- Admin
|-- AIT
|   |-- !DisabledServers
|   |-- ADK
|   |-- AFRI
|   |-- AKM
|   |-- AOR
|   |-- APR
|   |-- AQUA
|   |-- AUS
|   |-- BIO
|   |-- BIT
|   |   |-- BIT-DSG
|   |   |-- BIT-ISG
|   |   |-- BIT-NAT
|   |   |-- BIT-STAB
|   |-- CAS
|   |-- CIS
|   |-- CME
|   |-- COMP
|   |-- CROME
|   |-- DTUENT
|   |-- ELEC
|   |-- ELEK
|   |-- ENGTECH
|   |-- ENRGK
|   |-- FOOD
|   |-- FTNK
|   |-- FYS
|   |-- IMM
|   |-- KEMI
|   |-- KIT
|   |-- KT
|   |-- LLL
|   |-- MAN
|   |-- MEK
|   |-- NLAB
|   |-- NNFCB
|   |-- NTECH
|   |-- OESS
|   |-- RIT
|   |-- SPACE
|   |-- SUND
|   |-- SUS
|   |-- VIND
|   |-- WIND
|   |-- AIT-Clients
|   |   |-- Computers
|   |   |-- DisabledComputers
|   |   |-- DTU-Clients
|   |   |-- Groups
|   |   |-- Users
|   |   |-- YOYO
|   |-- AIT-FIT
|-- BBAR
|-- Builtin
|-- Computers
|-- Courses
|-- Default Users
|-- Delegations and Security
|-- DisabledDTUBaseUsers
|-- DTU-Computers
|-- DTU-Servers
|-- DTUBasen
|-- DTUBaseUsers (contains all employees)
|-- ForeignSecurityPrincipals
|-- GuestDTUdkusers
|-- Institutter
|   |-- ADK
|   |-- ADM
|   |-- AQUA
|   |-- Arcanic
|   |-- BIO
|   |-- BIOINF
|   |-- BYG
|   |-- CKIC
|   |-- CME
|   |-- COMP
|   |-- CROME
|   |-- DEIC
|   |-- DEKOM
|   |-- DTIC
|   |-- DTUENT
|   |-- ELEC
|   |-- ELEK
|   |-- ENGTECH
|   |-- ENRGK
|   |-- FOOD
|   |-- FYS
|   |-- KEMI
|   |-- KT
|   |-- LLL
|   |-- MAN
|   |-- NLAB
|   |-- NNFCB
|   |-- NTCH
|   |-- NTECH
|   |-- Offshore
|   |-- PKS
|   |-- RISOE
|   |-- SKY
|   |-- SPC
|   |-- SUND
|   |-- SUS
|   |-- TEM
|   |-- TRA
|   |-- VET
|   |-- WIND
|   |-- WNDSR
|-- LostAndFound
|-- Managed Service Accounts
|-- MBAR
|-- Microsoft Exchange Security Groups
|-- Program Data
|-- System
|-- Ukendte Computere
|-- Users
|-- Microsoft Exchange System Objects


### Examples

#### **Example 1: Retrieve All Computer Accounts in 'COMP'**

**User Request:**

"Retrieve all computer accounts under 'COMP' and include their operating system and last logon time."

**Query Parameters:**

- **`base_dn`**: `OU=COMP,OU=AIT,DC=win,DC=dtu,DC=dk`
- **`search_filter`**: `(objectClass=computer)`
- **`search_attributes`**: `operatingSystem,lastLogonTimestamp`
- **`limit`**: `100`
- **`excluded_attributes`**: `thumbnailPhoto`

#### **Example 2: List All Groups in 'ADM' with Their Members**

**User Request:**

"Get all groups in the 'ADM' organizational unit and list their members."

**Query Parameters:**

- **`base_dn`**: `OU=ADM,OU=Institutter,DC=win,DC=dtu,DC=dk`
- **`search_filter`**: `(objectClass=group)`
- **`search_attributes`**: `member`
- **`limit`**: `100`
- **`excluded_attributes`**: `thumbnailPhoto`

#### **Example 3: Fetch Disabled User Accounts in 'DTUBasen'**

**User Request:**

"Find all disabled user accounts under 'DTUBasen' and include their account names and statuses."

**Query Parameters:**

- **`base_dn`**: `OU=DTUBasen,DC=win,DC=dtu,DC=dk`
- **`search_filter`**: `(&(objectClass=user)(userAccountControl:1.2.840.113556.1.4.803:=2))`
- **`search_attributes`**: `sAMAccountName,userAccountControl`
- **`limit`**: `100`
- **`excluded_attributes`**: `thumbnailPhoto`

**Explanation:**

- The `userAccountControl` attribute is a bitmask representing user account properties.
- The value returned, such as `66050`, indicates various flags:
  - **66050** decomposes to:
    - `2` (`ACCOUNTDISABLE`): Account is disabled.
    - `65536` (`DONT_EXPIRE_PASSWORD`): Password does not expire.
    - `512` (`NORMAL_ACCOUNT`): Default account type.
- This means the account is disabled, the password does not expire, and it's a normal user account.

#### **Example 4: Retrieve Users Who Haven't Changed Password Since Before 2010**

**User Request:**

"Find all users who haven't set a new password since before 2010, including their account names, password last set dates, and account statuses."

**Query Parameters:**

- **`base_dn`**: `DC=win,DC=dtu,DC=dk`
- **`search_filter`**: `(&(objectClass=user)(pwdLastSet<=129069846000000000))`
- **`search_attributes`**: `sAMAccountName,pwdLastSet,userAccountControl`
- **`limit`**: `100`
- **`excluded_attributes`**: `thumbnailPhoto`

**Note:**

- `129069846000000000` is the NT time representation of January 1, 2010.
- Use the script below to calculate NT time for any date.

#### **Example 5: Get Users with Passwords Expiring Soon in 'ELEK'**

**User Request:**

"Retrieve all users in 'ELEK' whose passwords are set to expire in the next 7 days, including their names and password expiration dates."

**Query Parameters:**

- **`base_dn`**: `OU=ELEK,OU=Institutter,DC=win,DC=dtu,DC=dk`
- **`search_filter`**: `(&(objectClass=user)(pwdLastSet>=[DATE_LIMIT]))`
- **`search_attributes`**: `cn,pwdLastSet`
- **`limit`**: `100`
- **`excluded_attributes`**: `thumbnailPhoto`

*Note: Replace `[DATE_LIMIT]` with the NT time value for 7 days from now.*

---

### **Script to Convert Date to NT Time Format**

Here's a Python script to convert a standard date to NT time format used in LDAP queries:

```python
import datetime

def get_nt_time_from_date(year, month=1, day=1):
    # NT time starts on January 1, 1601
    nt_epoch = datetime.datetime(1601, 1, 1)
    target_date = datetime.datetime(year, month, day)
    delta = target_date - nt_epoch
    # NT time is measured in 100-nanosecond intervals
    nt_time = int(delta.total_seconds() * 10000000)
    return nt_time

# Getting NT time for the start of 2010
nt_time_2010 = get_nt_time_from_date(2010)

# Constructing LDAP query for users who haven't set a new password since before 2010
ldap_query_2010 = {
    "base_dn": "DC=win,DC=dtu,DC=dk",
    "search_filter": f"(&(objectClass=user)(pwdLastSet<={nt_time_2010}))",
    "search_attributes": "sAMAccountName,pwdLastSet,userAccountControl",
    "limit": 100,
    "excluded_attributes": "thumbnailPhoto"
}

print(ldap_query_2010)

userAccountControl Flags:

| Flag Name             | Hexadecimal | Decimal  | Description                                    |
|-----------------------|--------------|----------|------------------------------------------------|
| SCRIPT                | 0x0001       | 1        | Logon script is executed.                      |
| ACCOUNTDISABLE        | 0x0002       | 2        | Account is disabled.                           |
| HOMEDIR_REQUIRED      | 0x0008       | 8        | Home directory is required.                    |
| LOCKOUT               | 0x0010       | 16       | Account is currently locked out.               |
| PASSWD_NOTREQD        | 0x0020       | 32       | No password is required for this account.      |
| PASSWD_CANT_CHANGE    | 0x0040       | 64       | User cannot change password.                   |
| NORMAL_ACCOUNT        | 0x0200       | 512      | Default account type (normal user).            |
| DONT_EXPIRE_PASSWORD  | 0x10000      | 65536    | Password will not expire.                      |
| MNS_LOGON_ACCOUNT     | 0x20000      | 131072   | MNS logon account.                             |
| SMARTCARD_REQUIRED    | 0x40000      | 262144   | Smart card is required for logon.              |
| TRUSTED_FOR_DELEGATION| 0x80000      | 524288   | Account is trusted for delegation.             |
| USE_DES_KEY_ONLY      | 0x200000     | 2097152  | Use only DES encryption types for this account.|

# POLICIES
This policy ensures that inactive computer objects in the Active Directory are automatically disabled after 90 days (3 months) of inactivity. A computer account is considered inactive if it hasn't logged onto the domain within this period. This helps improve security by preventing unauthorized access from outdated devices and maintains efficiency by cleaning up unused accounts.

Key points:

Inactivity Period: Computer accounts inactive for 90 days will be disabled.
Account Removal: Disabled accounts may be permanently removed after 180 days.
Security: This process ensures that only active, current devices can access network resources.
Regular Activity: Both technical and non-technical users should ensure devices stay active to avoid automatic deactivation.
For technical implementation:

The $ageDisable variable sets the inactivity threshold to 90 days, while $ageRemove controls permanent removal after 180 days.
The policy excludes servers and focuses on computers in designated organizational units (OUs) like Institutter, BBAR, and AIT-FIT.

""",
        manual_parameters=[
            openapi.Parameter(
                'Authorization',  # name of the header
                in_=openapi.IN_HEADER,  # where the parameter is located
                description="Required. Must be in the format '<token>' or real token.",
                type=openapi.TYPE_STRING,  # type of the parameter
                required=True,  # if the header is required or not
                default='<token>'  # default value
            ),
            openapi.Parameter(
                name='base_dn',
                in_=openapi.IN_QUERY,
                description="Base DN for search. Example: 'DC=win,DC=dtu,DC=dk'",
                type=openapi.TYPE_STRING,
                required=True,
                default='DC=win,DC=dtu,DC=dk'
            ),
            openapi.Parameter(
                name='search_filter',
                in_=openapi.IN_QUERY,
                description="LDAP search filter. Example: '(objectClass=user)'",
                type=openapi.TYPE_STRING,
                required=True,
                default='(objectClass=user)'
            ),
            openapi.Parameter(
                name='search_attributes',
                in_=openapi.IN_QUERY,
                description="Comma-separated list of attributes to retrieve, or 'ALL_ATTRIBUTES' to fetch all. Example: 'cn,mail'",
                type=openapi.TYPE_STRING,
                required=False,
                default='ALL_ATTRIBUTES'
            ),
            openapi.Parameter(
                name='limit',
                in_=openapi.IN_QUERY,
                description="Limit for number of results. Example: 100",
                type=openapi.TYPE_INTEGER,
                required=False,
                default=100
            ),
            openapi.Parameter(
                name='excluded_attributes',
                in_=openapi.IN_QUERY,
                description="Comma-separated list of attributes to exclude from the results. Default is 'thumbnailPhoto'. Example: 'thumbnailPhoto,someOtherAttribute'",
                type=openapi.TYPE_STRING,
                required=False,
                default='thumbnailPhoto'
            ),
        ],
        responses={200: 'Successful response with the queried data'}
    )
    @action(detail=False, methods=['get'], url_path='query')
    def query(self, request):
        base_dn = request.query_params.get('base_dn')
        search_filter = request.query_params.get('search_filter')
        search_attributes = request.query_params.get('search_attributes', ALL_ATTRIBUTES)
        limit = request.query_params.get('limit', None)
        excluded_attributes = request.query_params.get('excluded_attributes', 'thumbnailPhoto').split(',')

        if limit is not None:
            limit = int(limit)

        if search_attributes == 'ALL_ATTRIBUTES' or search_attributes == '*' or search_attributes is None:
            search_attributes = ALL_ATTRIBUTES
        else:
            search_attributes = search_attributes.split(',')

        results = execute_active_directory_query(
            base_dn=base_dn,
            search_filter=search_filter,
            search_attributes=search_attributes,
            limit=limit,
            excluded_attributes=excluded_attributes
        )
        serialized_results = self.serialize_results(results)
        return Response(serialized_results)

    def serialize_value(self, value):
        """
        Convert LDAP attribute values to JSON serializable formats.
        """
        if isinstance(value, datetime.datetime):
            return value.isoformat()
        elif isinstance(value, bytes):
            return base64.b64encode(value).decode('utf-8')
        else:
            return value

    def serialize_results(self, results):
        """
        Serialize each attribute in the results list for JSON compatibility.
        """
        serialized_results = []
        for entry in results:
            serialized_entry = {}
            for key, values in entry.items():
                serialized_entry[key] = [self.serialize_value(value) for value in values]
            serialized_results.append(serialized_entry)
        return serialized_results




