from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import (
    Recipe,
    Ingredient,
    RecipeIngredient,
    Favorite,
    ShoppingCart,
)
from users.serializers import UserSerializer
from .omp_photo import Base64ImageField


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ["id", "name", "measurement_unit"]


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    name = serializers.CharField(
        source="ingredient.name", read_only=True
    )
    measurement_unit = serializers.CharField(
        source="ingredient.measurement_unit", read_only=True
    )
    amount = serializers.IntegerField()

    class Meta:
        model = RecipeIngredient
        fields = ["id", "name", "measurement_unit", "amount"]


class RecipeSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        many=True, source="recipeingredient_set"
    )
    image = Base64ImageField()
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = [
            "id", "author", "ingredients", "is_favorited",
            "is_in_shopping_cart", "name", "image", "text",
            "cooking_time"
        ]

    def get_is_favorited(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(
                user=request.user, recipe=obj
            ).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return ShoppingCart.objects.filter(
                user=request.user, recipe=obj
            ).exists()
        return False

    def create(self, validated_data):
        ingredients_data = validated_data.pop("recipeingredient_set", None)

        if not ingredients_data:
            raise ValidationError(
                {"ingredients": "Поле 'ingredients' не может быть пустым."}
            )

        validated_data.pop("author", None)
        recipe = Recipe.objects.create(
            author=self.context["request"].user, **validated_data
        )

        try:
            self._save_ingredients(recipe, ingredients_data)
        except ValidationError as e:
            recipe.delete()
            raise e

        return recipe

    def update(self, instance, validated_data):
        if "ingredients" not in self.initial_data:
            raise ValidationError({"ingredients": "Это поле необходимо."})

        ingredients_data = validated_data.pop("recipeingredient_set", None)

        instance.name = validated_data.get("name", instance.name)
        instance.text = validated_data.get("text", instance.text)
        instance.cooking_time = validated_data.get(
            "cooking_time", instance.cooking_time
        )

        if "image" in validated_data:
            instance.image = validated_data["image"]

        instance.save()

        if ingredients_data is not None:
            if not ingredients_data:
                raise ValidationError(
                    {"ingredients": "Поле 'ingredients' не может быть пустым."}
                )
            instance.recipeingredient_set.all().delete()
            self._save_ingredients(instance, ingredients_data)

        return instance

    def _save_ingredients(self, recipe, ingredients_data):
        seen_ingredients = set()
        for ingr in ingredients_data:
            ingredient_obj = ingr["id"]
            amount = ingr["amount"]

            if ingredient_obj in seen_ingredients:
                raise ValidationError(
                    {"ingredients": "Дубликаты запрещены."}
                )

            if amount < 1:
                raise ValidationError(
                    {"ingredients": "Количество ингредиентов "
                     "должно быть хотя бы 1."}
                )

            seen_ingredients.add(ingredient_obj)
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient=ingredient_obj,
                amount=amount
            )

    def validate_recipeingredient_set(self, value):
        if not value:
            raise ValidationError(
                {"ingredients": "Поле 'ingredients' не может быть пустым."}
            )

        seen_ingredients = set()
        for ingredient_data in value:
            ingredient = ingredient_data.get("id")
            amount = ingredient_data.get("amount")

            if not ingredient or amount is None:
                raise ValidationError(
                    {"ingredients": "Каждый ингредиент должен "
                     "иметь 'id' и 'amount'."}
                )

            if amount < 1:
                raise ValidationError(
                    {"ingredients": "Количество ингредиентов "
                     "должно быть хотя бы 1."}
                )

            if ingredient in seen_ingredients:
                raise ValidationError(
                    {"ingredients": "Дубликаты запрещены."}
                )

            seen_ingredients.add(ingredient)

        return value

    def validate_cooking_time(self, value):
        if value < 1:
            raise ValidationError("Время готовки минимум 1 минута.")
        return value


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ["id", "user", "recipe"]


class ShoppingCartSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingCart
        fields = ["id", "user", "recipe"]
