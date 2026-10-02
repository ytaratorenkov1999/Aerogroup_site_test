from django.contrib import admin

from .models import CrewMember


@admin.register(CrewMember)
class CrewMemberAdmin(admin.ModelAdmin):
    list_display = (
        "sap_number",
        "full_name",
        "first_name_ru",
        "first_name_en",
        "second_name",
        "email",
        "phone",
        "created_at",
    )
    search_fields = ("sap_number", "full_name", "email")
    list_filter = ("created_at",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)