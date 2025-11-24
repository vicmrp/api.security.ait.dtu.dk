"""Active Directory endpoints retaining their original behaviour."""

from __future__ import annotations

import base64
import datetime
from typing import Iterable, List, Optional

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from ldap3 import ALL_ATTRIBUTES
from rest_framework import status
from rest_framework.response import Response

from utils.api import SecuredAPIView
from utils.authentication import AzureAdTokenAuthentication
from rest_framework.authentication import TokenAuthentication

from .services import (
    execute_active_directory_query,
    execute_active_directory_query_assistant,
)


class ActiveDirectoryQueryAssistantView(SecuredAPIView):
    """Assist in building Active Directory queries from natural language."""

    authentication_classes = [AzureAdTokenAuthentication, TokenAuthentication]

    header_parameter = openapi.Parameter(
        "Authorization",
        in_=openapi.IN_HEADER,
        description="Type: Token YOUR_API_KEY",
        type=openapi.TYPE_STRING,
        required=True,
        default="",
    )

    user_prompt_body = openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "user_prompt": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="The user prompt for generating Active Directory query parameters.",
                example="Retrieve all disabled user accounts in 'DTUBasen' and include their account names and statuses.",
            )
        },
        required=["user_prompt"],
    )

    @swagger_auto_schema(
        manual_parameters=[header_parameter],
        request_body=user_prompt_body,
        operation_description="""
Active Directory Query Assistant

This assistant helps generate Active Directory query parameters based on user requests. It provides a structured JSON response with the necessary fields for querying the Active Directory. The 'explanation' field should contain a brief description of the query parameters generated.

Curl example:
```
curl --location --request POST 'http://api.security.ait.dtu.dk/active-directory/v1.0/query-assistant' \
    --header 'Authorization: Token YOUR_API_KEY' \
    --header 'Content-Type: application/json' \
    --data-raw '{
        "user_prompt": "Retrieve all disabled user accounts in 'DTUBasen' and include their account names and statuses."
    }'
```
""",
        responses={
            200: "Success",
            400: "Error: Invalid request.",
            404: "Error: No data found.",
            500: "Error: Internal server error",
        },
    )
    def post(self, request) -> Response:
        user_prompt = request.data.get("user_prompt")
        response = execute_active_directory_query_assistant(user_prompt=user_prompt)
        return Response(response, status=status.HTTP_200_OK)


class ActiveDirectoryQueryView(SecuredAPIView):
    """Perform an Active Directory LDAP query."""

    base_dn_param = openapi.Parameter(
        "base_dn",
        in_=openapi.IN_QUERY,
        description="Base distinguished name for the query. Example: 'OU=DTUBaseUsers,DC=win,DC=dtu,DC=dk'",
        type=openapi.TYPE_STRING,
        required=False,
    )

    search_filter_param = openapi.Parameter(
        "search_filter",
        in_=openapi.IN_QUERY,
        description="LDAP search filter. Example: '(objectClass=user)'",
        type=openapi.TYPE_STRING,
        required=False,
    )

    search_attributes_param = openapi.Parameter(
        "search_attributes",
        in_=openapi.IN_QUERY,
        description="Comma-separated list of attributes to retrieve, or 'ALL_ATTRIBUTES' to fetch all. Example: 'cn,mail'",
        type=openapi.TYPE_STRING,
        required=False,
        default="ALL_ATTRIBUTES",
    )

    limit_param = openapi.Parameter(
        "limit",
        in_=openapi.IN_QUERY,
        description="Maximum number of records to return.",
        type=openapi.TYPE_INTEGER,
        required=False,
    )

    excluded_attributes_param = openapi.Parameter(
        "excluded_attributes",
        in_=openapi.IN_QUERY,
        description="Comma-separated list of attributes to exclude from the response. Example: 'thumbnailPhoto'",
        type=openapi.TYPE_STRING,
        required=False,
        default="thumbnailPhoto",
    )

    @staticmethod
    def _serialize_value(value):
        if isinstance(value, datetime.datetime):
            return value.isoformat()
        if isinstance(value, bytes):
            return base64.b64encode(value).decode("utf-8")
        return value

    @classmethod
    def _serialize_results(cls, results: Iterable[dict]) -> List[dict]:
        serialised = []
        for entry in results:
            serialised_entry = {}
            for key, values in entry.items():
                serialised_entry[key] = [cls._serialize_value(value) for value in values]
            serialised.append(serialised_entry)
        return serialised

    @swagger_auto_schema(
        manual_parameters=[
            base_dn_param,
            search_filter_param,
            search_attributes_param,
            limit_param,
            excluded_attributes_param,
        ],
        operation_description="""
**Active Directory Query Endpoint**

This endpoint allows querying Active Directory based on given criteria. It provides flexibility in specifying which attributes to return, applying filters, and pagination control.

The synergy between the parameters allows for tailored queries:

- **`base_dn`**: Specifies the starting point within the AD structure.
- **`search_filter`**: Narrows down the objects based on specified conditions.
- **`search_attributes`**: Controls which attributes of the objects are retrieved.
- **`limit`**: Provides pagination capability.
- **`excluded_attributes`**: Refines the returned data by excluding specified attributes, enhancing query efficiency and relevance.
""",
        responses={200: "Successful response with the queried data"},
    )
    def get(self, request) -> Response:
        base_dn = request.query_params.get("base_dn")
        search_filter = request.query_params.get("search_filter")
        search_attributes = request.query_params.get("search_attributes", ALL_ATTRIBUTES)
        limit = request.query_params.get("limit")
        excluded_attributes = request.query_params.get("excluded_attributes", "thumbnailPhoto")

        if limit is not None:
            try:
                limit_value: Optional[int] = int(limit)
            except (TypeError, ValueError):
                limit_value = None
        else:
            limit_value = None

        if search_attributes in {None, "ALL_ATTRIBUTES", "*"}:
            attribute_list = ALL_ATTRIBUTES
        else:
            attribute_list = [item.strip() for item in search_attributes.split(",") if item.strip()]

        excluded_attribute_list = [item.strip() for item in excluded_attributes.split(",") if item.strip()]

        results = execute_active_directory_query(
            base_dn=base_dn,
            search_filter=search_filter,
            search_attributes=attribute_list,
            limit=limit_value,
            excluded_attributes=excluded_attribute_list,
        )

        serialised_results = self._serialize_results(results)
        return Response(serialised_results)
