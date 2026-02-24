from __future__ import annotations

from rest_framework import serializers


class MachineActionCommentSerializer(serializers.Serializer):
    comment = serializers.CharField(max_length=2048)


class IsolateMachineSerializer(MachineActionCommentSerializer):
    isolation_type = serializers.ChoiceField(
        choices=(
            ("Full", "Full"),
            ("Selective", "Selective"),
        ),
        default="Full",
    )


class LiveResponseCommandParamSerializer(serializers.Serializer):
    key = serializers.CharField(max_length=128)
    value = serializers.CharField()


class LiveResponseCommandSerializer(serializers.Serializer):
    type = serializers.CharField(max_length=64)
    params = LiveResponseCommandParamSerializer(many=True, required=False)


class RunLiveResponseSerializer(serializers.Serializer):
    commands = LiveResponseCommandSerializer(many=True)
    comment = serializers.CharField(max_length=2048, required=False, allow_blank=True)


class AdvancedHuntingQuerySerializer(serializers.Serializer):
    query = serializers.CharField()
