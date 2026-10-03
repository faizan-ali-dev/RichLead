from admin_dashboard.models import LoginActivity, SocialLink
from django.contrib import admin, messages
from django.contrib.auth import get_user_model

User = get_user_model()


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Manage customer access without exposing their workspace data."""

    list_display = ('display_name', 'email', 'email_verified', 'is_active', 'date_joined', 'last_login')
    list_filter = ('is_active', 'email_verified', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name', 'nickname')
    list_display_links = ('display_name', 'email')
    list_editable = ('is_active',)
    ordering = ('-date_joined',)
    readonly_fields = ('username', 'email', 'date_joined', 'last_login')
    fieldsets = (
        ('Account', {'fields': ('username', 'email', 'date_joined', 'last_login')}),
        ('Profile', {'fields': ('first_name', 'last_name', 'nickname')}),
        ('Access', {'fields': ('is_active', 'email_verified')}),
    )
    actions = ('activate_customer_accounts', 'deactivate_customer_accounts')

    @admin.display(description='Name', ordering='first_name')
    def display_name(self, user):
        return user.get_full_name().strip() or user.nickname or 'Unnamed user'

    def get_queryset(self, request):
        # Platform administrators are not customer accounts and must not be
        # suspendable from the customer-management table.
        return super().get_queryset(request).filter(is_staff=False, is_superuser=False)

    @admin.action(description='Activate selected customer accounts')
    def activate_customer_accounts(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} account(s) activated.', messages.SUCCESS)

    @admin.action(description='Suspend selected customer accounts')
    def deactivate_customer_accounts(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} account(s) suspended. Their workspace data was retained.', messages.SUCCESS)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ('public_label', 'platform', 'url', 'is_active', 'display_order', 'updated_at')
    list_filter = ('platform', 'is_active')
    search_fields = ('label', 'url')
    list_editable = ('is_active', 'display_order')
    ordering = ('display_order', 'id')
    readonly_fields = ('created_at', 'updated_at')
    fields = ('platform', 'label', 'url', 'is_active', 'display_order', 'created_at', 'updated_at')


@admin.register(LoginActivity)
class LoginActivityAdmin(admin.ModelAdmin):
    list_display = ('user_name', 'user_email', 'logged_in_at')
    list_filter = ('logged_in_at',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('user', 'logged_in_at')
    date_hierarchy = 'logged_in_at'
    ordering = ('-logged_in_at',)

    @admin.display(description='User')
    def user_name(self, activity):
        if not activity.user:
            return 'Deleted account'
        return activity.user.get_full_name().strip() or activity.user.nickname or 'Unnamed user'

    @admin.display(description='Email')
    def user_email(self, activity):
        return activity.user.email if activity.user else '—'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
