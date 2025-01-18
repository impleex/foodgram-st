from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.views import UserViewSet, LogoutView, CustomAuthToken
from recipes.views import RecipeViewSet, IngredientViewSet
from django.conf import settings
from django.conf.urls.static import static

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("recipes", RecipeViewSet, basename="recipe")
router.register("ingredients", IngredientViewSet, basename="ingredient")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path(
        "api/auth/token/login/",
        CustomAuthToken.as_view(),
        name="token_login",
    ),
    path(
        "api/auth/token/logout/",
        LogoutView.as_view(),
        name="token_logout",
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
