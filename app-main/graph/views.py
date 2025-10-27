"""Graph API endpoints that retain the original behaviour and documentation."""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.response import Response

from utils.api import SecuredAPIView

from .serializers import QuerySerializer
from .services import (
    execute_delete_software_mfa_method,
    execute_get_user,
    execute_identity_logon_events,
    execute_hunting_query,
    execute_list_user_authentication_methods,
    execute_microsoft_authentication_method,
    execute_phone_authentication_method,
)

logger = logging.getLogger(__name__)


def _extract_graph_error(response: Optional[Any]) -> str:
    """Return a human readable error description from a Graph response."""
    if response is None:
        return "No response received from Microsoft Graph."

    try:
        data = response.json()
    except ValueError:
        text = getattr(response, "text", "")
        return text or "Microsoft Graph returned an error without a body."

    if not isinstance(data, dict):
        return str(data)

    error = data.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        code = error.get("code")
        if message and code:
            return f"{code}: {message}"
        if message:
            return message
        if code:
            return code

    return str(data)


class GetUserView(SecuredAPIView):
    """Return information about a Microsoft Entra ID user."""

    authorization_header = openapi.Parameter(
        "Authorization",
        in_=openapi.IN_HEADER,
        description="Required. Must be in the format ''.",
        type=openapi.TYPE_STRING,
        required=True,
        default="",
    )

    user_path_param = openapi.Parameter(
        "user",
        in_=openapi.IN_PATH,
        description="The username requested for retrieval.",
        type=openapi.TYPE_STRING,
        required=True,
        default="vicre-test01@dtudk.onmicrosoft.com",
        override=True,
    )

    select_param = openapi.Parameter(
        "$select",
        in_=openapi.IN_QUERY,
        description="Optional. Specifies a subset of properties to include in the response.",
        type=openapi.TYPE_STRING,
        required=False,
    )

    @swagger_auto_schema(
        manual_parameters=[authorization_header, user_path_param, select_param],
        operation_description="""
Get the user info for the given username.

Microsoft Graph API documentation: https://learn.microsoft.com/en-us/graph/api/user-get?view=graph-rest-1.0&tabs=http

Curl example:
```
curl --location --request GET 'https://api.security.ait.dtu.dk/v1.0/graph/get-user/<user>' \
    --header 'Authorization: Token YOUR_API_KEY'
```

Response example:
```
{
    "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users/$entity",
    "businessPhones": [],
    "displayName": "vicre-test01",
    "givenName": "Victors test bruger",
    "jobTitle": "test bruger",
    "mail": "vicre-test01@dtudk.onmicrosoft.com",
    "mobilePhone": null,
    "officeLocation": null,
    "preferredLanguage": null,
    "surname": null,
    "userPrincipalName": "vicre-test01@dtudk.onmicrosoft.com",
    "id": "3358461b-2b36-4019-a2b7-2da92001cf7c"
}
```
""",
        responses={
            200: "Successfully got user",
            400: "Error: Bad request",
            404: "Error: Not found",
            500: "Error: Internal server error",
        },
    )
    def get(self, request, user: str) -> Response:
        select_param = request.GET.get("$select")
        payload, status_code = execute_get_user(user, select_param)
        return Response(payload, status=status_code)


class ListUserAuthenticationMethodsView(SecuredAPIView):
    """List all authentication methods configured for a user."""

    authorization_header = openapi.Parameter(
        "Authorization",
        in_=openapi.IN_HEADER,
        description="Required. Must be in the format ''.",
        type=openapi.TYPE_STRING,
        required=True,
        default="",
    )

    user_path_param = openapi.Parameter(
        "user_id__or__user_principalname",
        in_=openapi.IN_PATH,
        description="Get user authentication methods for the given user id.",
        type=openapi.TYPE_STRING,
        required=True,
        default="vicre-test01@dtudk.onmicrosoft.com",
        override=True,
    )

    @swagger_auto_schema(
        manual_parameters=[authorization_header, user_path_param],
        operation_description="""
Get the user authentication methods for the given user id.

Microsoft Graph API documentation: https://learn.microsoft.com/en-us/graph/api/microsoftauthenticatorauthenticationmethod-list?view=graph-rest-1.0&tabs=http

Response example using SMS as MFA method:
```
curl -X 'GET' \
    'http://localhost:6081/v1.0/graph/list/vicre-test01%40dtudk.onmicrosoft.com/authentication-methods' \
    -H 'accept: application/json' \
    -H 'Authorization: Token YOUR_API_KEY'
```

Response
```
{
    "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#users('vicre-test01%40dtudk.onmicrosoft.com')/authentication/methods",
    "value": [
        {
            "@odata.type": "#microsoft.graph.passwordAuthenticationMethod",
            "id": "28c10230-6103-485e-b985-444c60001490",
            "password": null,
            "createdDateTime": "2024-03-12T13:25:21Z"
        },
        {
            "@odata.type": "#microsoft.graph.microsoftAuthenticatorAuthenticationMethod",
            "id": "123e4441-eadf-4950-883d-fea123988824",
            "displayName": "iPhone 12",
            "deviceTag": "SoftwareTokenActivated",
            "phoneAppVersion": "6.8.3",
            "createdDateTime": null
        }
    ]
}
```
""",
        responses={
            200: "Successfully got user methods",
            400: "Error: Bad request",
            404: "Error: Not found",
            500: "Error: Internal server error",
        },
    )
    def get(self, request, user_id__or__user_principalname: str) -> Response:
        payload, status_code = execute_list_user_authentication_methods(
            user_id__or__user_principalname
        )
        return Response(payload, status=status_code)


class IdentityLogonEventsView(SecuredAPIView):
    """Return IdentityLogonEvents for a given user."""

    authorization_header = openapi.Parameter(
        "Authorization",
        in_=openapi.IN_HEADER,
        description="Required. Must be in the format ''.",
        type=openapi.TYPE_STRING,
        required=True,
        default="",
    )

    user_path_param = openapi.Parameter(
        "user",
        in_=openapi.IN_PATH,
        description="The user principal name to query.",
        type=openapi.TYPE_STRING,
        required=True,
        default="vicre@dtu.dk",
        override=True,
    )

    lookback_param = openapi.Parameter(
        "lookback",
        in_=openapi.IN_QUERY,
        description="Optional lookback window for the query (e.g. '7d', '48h'). Defaults to '7d'.",
        type=openapi.TYPE_STRING,
        required=False,
    )

    _LOOKBACK_PATTERN = re.compile(r"^\d+(?:\.\d+)?\s*(?:d|h|m)$", re.IGNORECASE)

    @swagger_auto_schema(
        manual_parameters=[authorization_header, user_path_param, lookback_param],
        operation_description="""
Fetch IdentityLogonEvents for the specified user within the provided lookback window.

Microsoft Graph API documentation: https://learn.microsoft.com/en-us/graph/api/security-runs-huntingquery?view=graph-rest-1.0

Curl example:
```
curl --location --request GET 'https://api.security.ait.dtu.dk/v1.0/graph/identitylogonevents/vicre%40dtu.dk?lookback=7d' \
    --header 'Authorization: Token YOUR_API_KEY'
```

Response example:
```
{
    "@odata.context": "https://graph.microsoft.com/v1.0/$metadata#microsoft.graph.security.huntingQueryResults",
    "schema": [...],
    "results": [...]
}
```
""",
        responses={
            200: "Identity logon events retrieved",
            400: "Error: Bad request",
            404: "Error: Not found",
            500: "Error: Internal server error",
        },
    )
    def get(self, request, user: str) -> Response:
        upn = (user or "").strip()
        if not upn:
            return Response(
                {
                    "status": "error",
                    "message": "User parameter cannot be empty.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        lookback = request.GET.get("lookback", "7d").strip()
        if lookback and not self._LOOKBACK_PATTERN.fullmatch(lookback):
            return Response(
                {
                    "status": "error",
                    "message": "Invalid lookback value. Use formats such as '7d', '24h', or '30m'.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload, status_code = execute_identity_logon_events(upn, lookback or "7d")
        except Exception:  # noqa: BLE001
            logger.exception("Failed to fetch IdentityLogonEvents for %s", upn)
            return Response(
                {
                    "status": "error",
                    "message": "Failed to fetch IdentityLogonEvents.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(payload, status=status_code)


class _BaseGraphDeleteView(SecuredAPIView):
    """Shared helpers for delete style Graph endpoints."""

    authorization_header = openapi.Parameter(
        "Authorization",
        in_=openapi.IN_HEADER,
        description="Required. Must be in the format ''.",
        type=openapi.TYPE_STRING,
        required=True,
        default="",
    )

    def _error_response(self, response: Optional[Any], message: str, status_code: Optional[int]) -> Response:
        detail = _extract_graph_error(response)
        return Response(
            {
                "status": "error",
                "message": message,
                "details": detail,
            },
            status=status_code or status.HTTP_502_BAD_GATEWAY,
        )


class DeleteSoftwareMfaView(_BaseGraphDeleteView):
    """Delete a software based MFA method for a user."""

    user_path_param = openapi.Parameter(
        "user_id__or__user_principalname",
        in_=openapi.IN_PATH,
        description="The username requested for deletion of software MFA.",
        type=openapi.TYPE_STRING,
        required=True,
        default="vicre-test01@dtudk.onmicrosoft.com",
        override=True,
    )

    method_path_param = openapi.Parameter(
        "software_oath_method_id",
        in_=openapi.IN_PATH,
        description="The authentication method ID for the software MFA solution to be deleted.",
        type=openapi.TYPE_STRING,
        required=True,
        default="00000000-0000-0000-0000-000000000000",
        override=True,
    )

    @swagger_auto_schema(
        manual_parameters=[_BaseGraphDeleteView.authorization_header, user_path_param, method_path_param],
        operation_description="""
Deletes a user's software-based MFA method, such as those using apps like Google Authenticator.

Curl example:
```
curl -X 'DELETE' \
    'http://localhost:6081/v1.0/graph/users/vicre-test01%40dtudk.onmicrosoft.com/software-authentication-methods/38870367-9eb1-4568-9056-23c141f777de' \
    -H 'accept: application/json' \
    -H 'Authorization: Token YOUR_API_KEY'
```

Response: 204 No content
""",
        responses={
            204: "Successfully deleted software MFA method",
            400: "Error: Bad request",
            404: "Error: Not found",
            500: "Error: Internal server error",
        },
    )
    def delete(
        self,
        request,
        user_id__or__user_principalname: str,
        software_oath_method_id: str,
    ) -> Response:
        try:
            response, status_code = execute_delete_software_mfa_method(
                user_id__or__user_principalname,
                software_oath_method_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to delete software MFA for %s",
                user_id__or__user_principalname,
            )
            return Response(
                {
                    "status": "error",
                    "message": "Failed to delete software MFA.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if status_code == status.HTTP_204_NO_CONTENT:
            return Response(status=status.HTTP_204_NO_CONTENT)

        return self._error_response(
            response,
            "Microsoft Graph did not confirm deletion.",
            status_code,
        )


class DeleteMfaView(_BaseGraphDeleteView):
    """Delete a Microsoft Authenticator method for a user."""

    user_path_param = openapi.Parameter(
        "user_id__or__user_principalname",
        in_=openapi.IN_PATH,
        description="The username requested for deletion of MFA.",
        type=openapi.TYPE_STRING,
        required=True,
        default="vicre-test01@dtudk.onmicrosoft.com",
        override=True,
    )

    method_path_param = openapi.Parameter(
        "microsoft_authenticator_method_id",
        in_=openapi.IN_PATH,
        description="The authentication method id for the MFA solution to be deleted.",
        type=openapi.TYPE_STRING,
        required=True,
        default="00000000-0000-0000-0000-000000000000",
        override=True,
    )

    @swagger_auto_schema(
        manual_parameters=[_BaseGraphDeleteView.authorization_header, user_path_param, method_path_param],
        operation_description="""
Incoming user MFA solutions will be deleted, thereby giving users space to re-enable MFA by deleting their MFA solution on the app, then visiting office.com and signing in with <user>@dtu.dk to re-enable MFA.

Microsoft Graph API documentation: https://learn.microsoft.com/en-us/graph/api/microsoftauthenticatorauthenticationmethod-delete?view=graph-rest-1.0&tabs=http

Curl example:
```
curl -X 'DELETE' \
    'http://localhost:6081/v1.0/graph/users/vicre-test01%40dtudk.onmicrosoft.com/microsoft-authentication-methods/171397f2-804e-4664-8ede-c4b3adf6bbb0' \
    -H 'accept: application/json' \
    -H 'Authorization: Token YOUR_API_KEY'
```

Response: 204 No content
""",
        responses={
            204: "Successfully deleted MFA",
            400: "Error: Bad request",
            404: "Error: Not found",
            500: "Error: Internal server error",
        },
    )
    def delete(
        self,
        request,
        user_id__or__user_principalname: str,
        microsoft_authenticator_method_id: str,
    ) -> Response:
        try:
            response, status_code = execute_microsoft_authentication_method(
                user_id__or__user_principalname,
                microsoft_authenticator_method_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to delete Microsoft authenticator method for %s",
                user_id__or__user_principalname,
            )
            return Response(
                {
                    "status": "error",
                    "message": "Failed to delete authentication method.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if status_code == status.HTTP_204_NO_CONTENT:
            return Response(status=status.HTTP_204_NO_CONTENT)

        return self._error_response(
            response,
            "Microsoft Graph did not confirm deletion.",
            status_code,
        )


class DeletePhoneView(_BaseGraphDeleteView):
    """Delete a phone based MFA method for a user."""

    user_path_param = openapi.Parameter(
        "user_id__or__user_principalname",
        in_=openapi.IN_PATH,
        description="The username requested for deletion of phone MFA.",
        type=openapi.TYPE_STRING,
        required=True,
        default="vicre-test01@dtudk.onmicrosoft.com",
        override=True,
    )

    method_path_param = openapi.Parameter(
        "phone_authenticator_method_id",
        in_=openapi.IN_PATH,
        description="The authentication method id for the phone solution to be deleted.",
        type=openapi.TYPE_STRING,
        required=True,
        default="00000000-0000-0000-0000-000000000000",
        override=True,
    )

    @swagger_auto_schema(
        manual_parameters=[_BaseGraphDeleteView.authorization_header, user_path_param, method_path_param],
        operation_description="""
Incoming user phone based MFA solutions will be deleted, thereby giving users space to re-enable MFA by deleting their phone authentication method and then re-registering it.

Microsoft Graph API documentation: https://learn.microsoft.com/en-us/graph/api/phoneauthenticationmethod-delete?view=graph-rest-1.0&tabs=http

Curl example:
```
curl -X 'DELETE' \
    'http://localhost:6081/v1.0/graph/users/vicre-test01%40dtudk.onmicrosoft.com/phone-authentication-methods/171397f2-804e-4664-8ede-c4b3adf6bbb0' \
    -H 'accept: application/json' \
    -H 'Authorization: Token YOUR_API_KEY'
```

Response: 204 No content
""",
        responses={
            204: "Successfully deleted phone MFA",
            400: "Error: Bad request",
            404: "Error: Not found",
            500: "Error: Internal server error",
        },
    )
    def delete(
        self,
        request,
        user_id__or__user_principalname: str,
        phone_authenticator_method_id: str,
    ) -> Response:
        try:
            response, status_code = execute_phone_authentication_method(
                user_id__or__user_principalname,
                phone_authenticator_method_id,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to delete phone authentication method for %s",
                user_id__or__user_principalname,
            )
            return Response(
                {
                    "status": "error",
                    "message": "Failed to delete phone authentication method.",
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if status_code == status.HTTP_204_NO_CONTENT:
            return Response(status=status.HTTP_204_NO_CONTENT)

        return self._error_response(
            response,
            "Microsoft Graph did not confirm deletion.",
            status_code,
        )


class HuntingQueryView(SecuredAPIView):
    """Execute a hunting query."""

    authorization_header = openapi.Parameter(
        "Authorization",
        in_=openapi.IN_HEADER,
        description="Required. Must be in the format ''.",
        type=openapi.TYPE_STRING,
        required=True,
    )

    content_type_parameter = openapi.Parameter(
        "Content-Type",
        in_=openapi.IN_HEADER,
        description="Required. Must be 'application/json'.",
        type=openapi.TYPE_STRING,
        required=True,
    )

    request_body = openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["Query"],
        properties={
            "Query": openapi.Schema(
                type=openapi.TYPE_STRING,
                example="<kql query>",
            )
        },
    )

    @swagger_auto_schema(
        manual_parameters=[authorization_header, content_type_parameter],
        request_body=request_body,
        operation_description="Hunting query description",
        responses={
            200: "ComputerInfoSerializer()",
            400: "Error: Bad request",
            404: "Error: Not found",
            500: "Error: Internal server error",
        },
    )
    def post(self, request) -> Response:
        serializer = QuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        query = serializer.validated_data["Query"]
        try:
            payload, status_code = execute_hunting_query(query)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to execute hunting query")
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(payload, status=status_code)
