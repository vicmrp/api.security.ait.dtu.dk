from rest_framework import serializers


class QuerySerializer(serializers.Serializer):
    Query = serializers.CharField()