from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponseRedirect
from recipes.models import Recipe


def redirect_short_link(request, recipe_id):
    if Recipe.objects.filter(id=recipe_id).exists():
        return HttpResponseRedirect(f'/api/recipes/{recipe_id}/')
    return HttpResponseRedirect('/api/recipes/')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('r/<int:recipe_id>/', redirect_short_link, name='recipe-short-link'),
]
