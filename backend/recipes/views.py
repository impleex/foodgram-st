from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import (
    FilterSet,
    CharFilter,
    DjangoFilterBackend,
)
from django.conf import settings
from django.db.models import Sum
from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils.crypto import get_random_string

from .models import Recipe, Ingredient, Favorite, ShoppingCart
from .serializers import RecipeSerializer, IngredientSerializer


class IngredientFilter(FilterSet):
    name = CharFilter(field_name="name", lookup_expr="istartswith")

    class Meta:
        model = Ingredient
        fields = ["name"]


class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all().order_by("name")
    serializer_class = IngredientSerializer
    filterset_class = IngredientFilter
    filter_backends = [DjangoFilterBackend]

    def create(self, request, *args, **kwargs):
        return Response(
            {"detail": "Метод POST не разрешен для этой конечной точки."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Метод PUT не разрешен для этой конечной точки."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Метод PATCH не разрешен для этой конечной точки."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Метод DELETE не разрешен для этой конечной точки."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["author"]

    def get_permissions(self):
        if self.action in [
            "create",
            "update",
            "partial_update",
            "destroy",
            "shopping_cart",
            "download_shopping_cart",
        ]:
            return [IsAuthenticated()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def update(self, request, *args, **kwargs):
        recipe = self.get_object()
        if recipe.author != request.user:
            return Response(
                {"detail": "У вас нет разрешения на редактирование рецепта."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        recipe = self.get_object()
        if recipe.author != request.user:
            return Response(
                {"detail": "Вы не можете удалить чужой рецепт."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        is_in_shopping_cart = self.request.query_params.get(
            "is_in_shopping_cart"
        )
        if is_in_shopping_cart is not None and user.is_authenticated:
            if is_in_shopping_cart == "1":
                queryset = queryset.filter(in_shopping_cart__user=user)
            elif is_in_shopping_cart == "0":
                queryset = queryset.exclude(in_shopping_cart__user=user)

        is_favorited = self.request.query_params.get("is_favorited")
        if is_favorited is not None and user.is_authenticated:
            if is_favorited == "1":
                queryset = queryset.filter(favorited_by__user=user)
            elif is_favorited == "0":
                queryset = queryset.exclude(favorited_by__user=user)

        return queryset

    @action(detail=True, methods=["get"], url_path="get-link")
    def get_link(self, request, pk=None):
        short_link = f"{settings.BASE_URL}/short/{get_random_string(6)}"
        return Response({"short-link": short_link}, status=200)

    @action(
        detail=True, methods=["post", "delete"], url_path="favorite",
        permission_classes=[IsAuthenticated]
    )
    def favorite(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)

        if request.method == "POST":
            favorite, created = Favorite.objects.get_or_create(
                user=request.user, recipe=recipe
            )
            if not created:
                return Response(
                    {"error": "Этот рецепт уже в избранном."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            data = {
                "id": recipe.id,
                "name": recipe.name,
                "image": request.build_absolute_uri(recipe.image.url),
                "cooking_time": recipe.cooking_time,
            }
            return Response(data, status=status.HTTP_201_CREATED)

        deleted, _ = Favorite.objects.filter(
            user=request.user, recipe=recipe
        ).delete()
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {"error": "Этот рецепт отсутствует в избранном."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(
        detail=True, methods=["post", "delete"], url_path="shopping_cart",
        permission_classes=[IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        recipe = get_object_or_404(Recipe, pk=pk)

        if request.method == "POST":
            cart_item, created = ShoppingCart.objects.get_or_create(
                user=request.user, recipe=recipe
            )
            if not created:
                return Response(
                    {"error": "Этот рецепт уже есть в корзине."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            data = {
                "id": recipe.id,
                "name": recipe.name,
                "image": request.build_absolute_uri(recipe.image.url),
                "cooking_time": recipe.cooking_time,
            }
            return Response(data, status=status.HTTP_201_CREATED)

        deleted, _ = ShoppingCart.objects.filter(
            user=request.user, recipe=recipe
        ).delete()
        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {"error": "Этот рецепт отсутствует в корзине."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=["get"], url_path="download_shopping_cart")
    def download_shopping_cart(self, request):
        user = request.user
        shopping_cart = ShoppingCart.objects.filter(
            user=user
        ).select_related("recipe__ingredients")

        if not shopping_cart.exists():
            return Response(
                {"error": "Корзина покупок пуста."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ingredients = shopping_cart.values(
            "recipe__ingredients__name",
            "recipe__ingredients__measurement_unit"
        ).annotate(amount=Sum("recipe__recipeingredient__amount"))

        shopping_list_text = "Список покупок:\n\n"
        for item in ingredients:
            shopping_list_text += (
                f"{item['recipe__ingredients__name']} "
                f"({item['recipe__ingredients__measurement_unit']}): "
                f"{item['amount']}\n"
            )

        response = HttpResponse(shopping_list_text, content_type="text/plain")
        response["Content-Disposition"] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response
