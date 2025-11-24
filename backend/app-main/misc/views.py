from rest_framework import viewsets
from rest_framework.response import Response
from datetime import datetime
from rest_framework.permissions import IsAuthenticated
from utils.authentication import AzureAdTokenAuthentication
from rest_framework.authentication import TokenAuthentication

class JsonValueExtractor(viewsets.ViewSet):

    authentication_classes = [AzureAdTokenAuthentication, TokenAuthentication]  # Require token authentication for this view
    permission_classes = [IsAuthenticated]  # Require authenticated user for this view


    def create(self, request, *args, **kwargs):
        try:
            # check if parameter is true
            to_scalar = request.query_params.get('toscalar', 'false')

            # get the json data from body.
            data = request.data

            # Try to extract Query property
            query = data['object']['properties']['alerts'][0]['properties']['additionalData']['Query']

            if to_scalar.lower() == 'true':
                response = query
            else:
                response = {'Query': query}
                

            data = request.data
            query = data['object']['properties']['alerts'][0]['properties']['additionalData']['Query']

            return Response(response)
        except KeyError:
            return Response({'error': 'Failed to extract Query property. Check the JSON structure.'})


class GenerateEmail(viewsets.ViewSet):
    def create(self, request, *args, **kwargs):        
        try:
            # check if parameter is true
            to_scalar = request.query_params.get('toscalar', 'false')

            # get the json data from body.
            data = request.data

            app_display_name = data['results'][0]['AppDisplayName']
            city = data['results'][0]['City']
            country_or_region = data['results'][0]['CountryOrRegion']
            fullname = data['results'][0]['Fullname']
            ip_address = data['results'][0]['IPAddress']
            state = data['results'][0]['State']
            time_generated = data['results'][0]['TimeGenerated'] # '2023-12-07T14:03:38.0418848Z' -> '%Y-%m-%dT%H:%M:%S.%fZ'
            # Truncate the last digit from the seconds fraction
            time_generated = time_generated[:-2] + 'Z'
            time_generated_datetime = datetime.strptime(time_generated, '%Y-%m-%dT%H:%M:%S.%fZ')
            user_pricipal_name = data['results'][0]['City']


            # Subject: Security Alert: MFA Request Decline Notification

            # Dear [Fullname],

            # This is an automated security notification. A declined Multi-Factor Authentication (MFA) request associated with your account has been recorded:

            # Time and Date: [TimeGenerated]
            # Application: [AppDisplayName]
            # User ID: [UserPrincipalName]
            # IP Address: [IPAddress]
            # Location: [City], [State], [CountryOrRegion]
            # Action Required:

            # If you recognize this event, no further action is needed.
            # If you do not recognize this event, please change your password immediately at password.dtu.dk for security reasons.
            # For any concerns, contact our support team.

            # [Your Organization’s Security Team]
            '''
            Dear {fullname},
            <br>\n
            <br>\n
            This is an automated security notification. A declined Multi-Factor Authentication (MFA) request associated with your account has been recorded:
            <br>\n
            <br>\n
            <strong>Time and Date</strong>: {time_generated_datetime}
            <br>\n
            <strong>Application</strong>: {app_display_name}
            <br>\n
            <strong>User ID</strong>: {user_pricipal_name}
            <br>\n
            <strong>IP Address</strong>: {ip_address}
            <br>\n
            <strong>Location</strong>: {city}, {state}, {country_or_region}
            <br>\n
            <strong>Action Required</strong>:
            <br>\n
            <br>\n
            If you recognize this event, no further action is needed.
            <br>\n
            If you do not recognize this event, please change your password immediately at password.dtu.dk for security reasons.
            <br>\n
            For any concerns, contact our support team.
            <br>\n
            <br>\n
            AITSOC
            '''



#             mail_string = f"""
# Subject: Security Alert: MFA Request Decline Notification

# Dear {fullname},

# This is an automated security notification. A declined Multi-Factor Authentication (MFA) request associated with your account has been recorded:

# Time and Date: {time_generated_datetime}
# Application: {app_display_name}
# User ID: {user_pricipal_name}
# IP Address: {ip_address}
# Location: {city}, {state}, {country_or_region}
# Action Required:

# If you recognize this event, no further action is needed.
# If you do not recognize this event, please change your password immediately at password.dtu.dk for security reasons.
# For any concerns, contact our support team.

# [Your Organizations Security Team]
# """


            mail_string = f"""
            Dear {fullname},
            <br>\n
            <br>\n
            This is an automated security notification. A declined Multi-Factor Authentication (MFA) request associated with your account has been recorded:
            <br>\n
            <br>\n
            <strong>Time and Date</strong>: {time_generated_datetime}
            <br>\n
            <strong>Application</strong>: {app_display_name}
            <br>\n
            <strong>User ID</strong>: {user_pricipal_name}
            <br>\n
            <strong>IP Address</strong>: {ip_address}
            <br>\n
            <strong>Location</strong>: {city}, {state}, {country_or_region}
            <br>\n
            <strong>Action Required</strong>:
            <br>\n
            <br>\n
            If you recognize this event, no further action is needed.
            <br>\n
            If you do not recognize this event, please change your password immediately at password.dtu.dk for security reasons.
            <br>\n
            For any concerns, contact our support team.
            <br>\n
            <br>\n
            AITSOC
"""


            if to_scalar.lower() == 'true':
                response = {'mail_string': mail_string}
            else:
                response = mail_string

            data = request.data
            

            return Response(response)
        except KeyError:
            return Response({'error': 'Failed to extract Query property. Check the JSON structure.'})



