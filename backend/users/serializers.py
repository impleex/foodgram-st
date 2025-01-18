from rest_framework import serializers
from django.contrib.auth import authenticate

from .models import User, Subscription
from .omp_photo import Base64ImageField


class EmailAuthTokenSerializer(serializers.Serializer):
    email = serializers.EmailField(label="Email")
    password = serializers.CharField(
        label="Password",
        style={"input_type": "password"}
    )

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            user = authenticate(username=email, password=password)
            if not user:
                raise serializers.ValidationError(
                    "Неверные учётные данные",
                    code="authorization"
                )
            if not user.is_active:
                raise serializers.ValidationError(
                    "Пользователь деактивирован",
                    code="authorization"
                )
        else:
            raise serializers.ValidationError(
                "Требуется email и password",
                code="authorization"
            )

        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(required=False, allow_null=True)
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_subscribed",
            "avatar",
        ]

    def get_avatar(self, obj):
        return None

    def get_is_subscribed(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Subscription.objects.filter(
                user=request.user,
                author=obj
            ).exists()
        return False


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=150,
        error_messages={
            "required": "Поле 'first_name' обязательно.",
            "blank": "Поле 'first_name' не может быть пустым.",
            "max_length": (
                "Максимальная длина поля 'first_name' - 150 символов."
            ),
        },
    )
    last_name = serializers.CharField(
        required=True,
        allow_blank=False,
        max_length=150,
        error_messages={
            "required": "Поле 'last_name' обязательно.",
            "blank": "Поле 'last_name' не может быть пустым.",
            "max_length": (
                "Максимальная длина поля 'last_name' - 150 символов."
            ),
        },
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
        ]

    def create(self, validated_data):
        user = User(
            username=validated_data["username"],
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
        )
        user.set_password(validated_data["password"])
        user.save()
        return user


class SubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscription
        fields = ["id", "user", "author"]
