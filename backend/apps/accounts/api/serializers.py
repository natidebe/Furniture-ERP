from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.accounts.models import ROLE_DEFAULT_PERMISSIONS, ERPPermission, TelegramLinkToken, User


class MeSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="full_name")
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "name", "role", "home_location", "permissions"]

    def get_permissions(self, user) -> list[str]:
        return user.effective_erp_permissions()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False,
                                     style={"input_type": "password"})
    # Omit on create or role change to get the role's defaults.
    permissions = serializers.ListField(
        source="erp_permissions", required=False,
        child=serializers.ChoiceField(choices=ERPPermission.choices))

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "phone", "role", "home_location",
                  "telegram_id", "is_active", "permissions", "allowed_payment_accounts",
                  "password", "date_joined", "last_login"]
        read_only_fields = ["telegram_id", "date_joined", "last_login"]

    def validate(self, attrs):
        password = attrs.get("password")
        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "This field is required."})
        if password:
            validate_password(password, user=self.instance)
        return attrs


class LinkCodeSerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="token")

    class Meta:
        model = TelegramLinkToken
        fields = ["code", "expires_at"]


class ERPPermissionSerializer(serializers.Serializer):
    codename = serializers.CharField()
    label = serializers.CharField()
    default_for_roles = serializers.ListField(child=serializers.CharField())

    @staticmethod
    def all_permissions() -> list[dict]:
        return [
            {"codename": p.value, "label": p.label,
             "default_for_roles": [role for role, perms in ROLE_DEFAULT_PERMISSIONS.items()
                                   if p.value in perms]}
            for p in ERPPermission
        ]
