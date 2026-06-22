from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration.
    Validates email uniqueness and password confirmation.
    """

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
        help_text="Minimum 8 characters.",
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        help_text="Must match password.",
    )

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "password", "confirm_password"]
        read_only_fields = ["id"]

    def validate_email(self, value):
        """Ensure email is lowercase and unique."""
        email = value.lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return email

    def validate(self, attrs):
        """Check that password and confirm_password match."""
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data):
        """Remove confirm_password and create user with hashed password."""
        validated_data.pop("confirm_password")
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data.get("full_name", ""),
        )
        return user


class LoginSerializer(serializers.Serializer):
    """
    Serializer for user login via email + password.
    """

    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        email = attrs.get("email", "").lower()
        password = attrs.get("password")

        if not email or not password:
            raise serializers.ValidationError("Email and password are required.")

        user = authenticate(
            request=self.context.get("request"),
            email=email,
            password=password,
        )

        if not user:
            raise serializers.ValidationError(
                "Invalid email or password. Please try again."
            )

        if not user.is_active:
            raise serializers.ValidationError(
                "This account has been deactivated."
            )

        attrs["user"] = user
        return attrs


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for returning and updating authenticated user profile data.
    """

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "bio", "profile_picture", "is_active", "date_joined"]
        read_only_fields = ["id", "email", "is_active", "date_joined"]
