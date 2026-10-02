from django.contrib import admin

from .models import CrewMember, Passenger


@admin.register(CrewMember)
class CrewMemberAdmin(admin.ModelAdmin):
    list_display = (
        "sap_number",
        "full_name",
        "full_name_en",
        "first_name",
        "last_name",
        "email",
        "instructor_check",
        "created_at",
    )
    search_fields = ("sap_number", "full_name", "email")
    list_filter = ("created_at",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


@admin.register(Passenger)
class PassengerAdmin(admin.ModelAdmin):
    list_display = (
        "document_number",
        "fake_document_number",
        "last_name",
        "first_name",
        "middle_name",
        "birth_date",
        "created_at",
    )
    search_fields = ("document_number", "fake_document_number", "last_name")
    list_filter = ("created_at",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)
