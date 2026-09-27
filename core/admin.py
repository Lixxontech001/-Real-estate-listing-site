from django.contrib import admin

from .models import Address, Country, State


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    search_fields = ["name", "shortcut"]
    list_display = ("name", "shortcut")
    ordering = ["name"]


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    search_fields = ["name", "country__name"]
    autocomplete_fields = ["country"]
    list_display = ("name", "country", "shortcut")
    list_display_links = ("name",)
    list_editable = ("shortcut",)
    list_filter = ["country"]
    ordering = ["country__name", "name"]


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    search_fields = ["street", "city", "state__name", "zipcode"]
    autocomplete_fields = ["state"]
    list_display = ("street", "hn", "zipcode", "city", "state")
    list_filter = ["state__country", "state"]
    ordering = ["city", "street"]
