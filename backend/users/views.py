import logging
import base64
import uuid

from django.core.files.base import ContentFile
from django.db.models import Count
from django.contrib.auth.hashers import check_password
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.pagination import PageNumberPagination

from recipes.models import Recipe
from .models import User, Subscription
from .serializers import (
    UserSerializer,
    UserCreateSerializer,
    EmailAuthTokenSerializer,
)

logger = logging.getLogger(__name__)


class CustomPagination(PageNumberPagination):
    page_size = 6
    page_size_query_param = "limit"
    max_page_size = 100


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_serializer_context(self):
        return {"request": self.request}

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated]
    )
    def me(self, request):
        user = request.user
        serializer = self.get_serializer(user)
        return Response(
            serializer.data,
            status=200
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsAuthenticated]
    )
    def set_password(self, request):
        user = request.user
        old_password = request.data.get("current_password")
        new_password = request.data.get("new_password")

        if not old_password or not new_password:
            return Response(
                {
                    "error": (
                        "Поля 'current_password' и 'new_password' "
                        "обязательны."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not check_password(old_password, user.password):
            return Response(
                {"error": "Текущий пароль указан неверно."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if old_password == new_password:
            return Response(
                {"error": "Новый пароль не должен совпадать с текущим."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=["put", "delete"],
        url_path="me/avatar",
        permission_classes=[IsAuthenticated],
    )
    def update_avatar(self, request):
        if request.method == "PUT":
            avatar_base64 = request.data.get("avatar")
            if not avatar_base64:
                return Response(
                    {"error": "Поле 'avatar' обязательно."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                format_part, imgstr = avatar_base64.split(";base64,")
                ext = format_part.split("/")[-1]
                file_name = f"{uuid.uuid4()}.{ext}"
                request.user.avatar.save(
                    file_name,
                    ContentFile(base64.b64decode(imgstr)),
                    save=True
                )
                return Response(
                    {
                        "avatar": request.build_absolute_uri(
                            request.user.avatar.url
                        )
                    },
                    status=status.HTTP_200_OK,
                )
            except Exception as exc:
                logger.error(
                    f"Ошибка обновления аватара: {exc}"
                )
                return Response(
                    {"error": "Не удалось обновить аватар."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        if request.method == "DELETE":
            if not request.user.avatar:
                return Response(
                    {"detail": "Аватар отсутствует."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            request.user.avatar.delete()
            request.user.save()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post", "delete"],
        permission_classes=[IsAuthenticated]
    )
    def subscribe(self, request, pk=None):
        user = request.user
        author = self.get_object()

        if request.method == "DELETE":
            subscription = Subscription.objects.filter(
                user=user,
                author=author
            )
            if not subscription.exists():
                return Response(
                    {"error": "Вы не подписаны на этого пользователя."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            subscription.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        if user == author:
            return Response(
                {"error": "Вы не можете подписаться на самого себя."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subscription, created = Subscription.objects.get_or_create(
            user=user,
            author=author
        )
        if not created:
            return Response(
                {"error": "Вы уже подписаны на этого пользователя."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        recipes_limit = request.query_params.get("recipes_limit")
        try:
            recipes_limit = (
                int(recipes_limit)
                if recipes_limit is not None
                else None
            )
        except ValueError:
            recipes_limit = None

        author_data = UserSerializer(
            author,
            context={"request": request}
        ).data
        author_data["recipes_count"] = Recipe.objects.filter(
            author=author
        ).count()

        recipes_queryset = Recipe.objects.filter(author=author)
        if recipes_limit is not None:
            recipes_queryset = recipes_queryset[:recipes_limit]

        author_data["recipes"] = [
            {
                "id": recipe.id,
                "name": recipe.name,
                "image": request.build_absolute_uri(
                    recipe.image.url
                ),
                "cooking_time": recipe.cooking_time,
            }
            for recipe in recipes_queryset
        ]

        return Response(author_data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"])
    def unsubscribe(self, request, pk=None):
        user = request.user
        author = self.get_object()
        Subscription.objects.filter(user=user, author=author).delete()
        return Response({"status": "unsubscribed"})

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated]
    )
    def subscriptions(self, request):
        user = request.user
        subscriptions = User.objects.filter(
            subscribers__user=user
        ).annotate(recipes_count=Count("recipes"))

        paginator = CustomPagination()
        result_page = paginator.paginate_queryset(subscriptions, request)

        response_data = []
        recipes_limit = request.query_params.get("recipes_limit")
        try:
            recipes_limit = (
                int(recipes_limit)
                if recipes_limit is not None
                else None
            )
        except ValueError:
            recipes_limit = None

        for author in result_page:
            author_data = UserSerializer(
                author,
                context={"request": request}
            ).data
            author_data["recipes_count"] = author.recipes_count
            recipes_queryset = Recipe.objects.filter(author=author)
            if recipes_limit is not None:
                recipes_queryset = recipes_queryset[:recipes_limit]

            author_data["recipes"] = [
                {
                    "id": recipe.id,
                    "name": recipe.name,
                    "image": request.build_absolute_uri(
                        recipe.image.url
                    ),
                    "cooking_time": recipe.cooking_time,
                }
                for recipe in recipes_queryset
            ]
            response_data.append(author_data)

        return paginator.get_paginated_response(response_data)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            Token.objects.get(user=request.user).delete()
            return Response(status=204)
        except Token.DoesNotExist:
            return Response(
                {"detail": "Токен для данного пользователя не найден."},
                status=400
            )
        except Exception as exc:
            logger.error(f"Ошибка при выходе: {exc}")
            return Response({"detail": str(exc)}, status=400)


class CustomAuthToken(ObtainAuthToken):
    serializer_class = EmailAuthTokenSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"auth_token": token.key})
