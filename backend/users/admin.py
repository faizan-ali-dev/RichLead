from django.contrib.auth import get_user_model
from django.contrib import admin

User = get_user_model()


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Let trusted staff suspend accounts without exposing credential hashes."""

    list_display = ("username", "email", "is_active", "is_staff", "date_joined")
    list_filter = ("is_active", "is_staff", "date_joined")
    search_fields = ("username", "email")
    readonly_fields = ("username", "email", "date_joined")
    fieldsets = (
        (None, {"fields": ("username", "email", "is_active", "date_joined")}),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
