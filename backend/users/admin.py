import uuid

from admin_dashboard.models import LoginActivity, PlatformTeamMember, SocialLink
from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.auth.password_validation import validate_password
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

User = get_user_model()


class PlatformTeamMemberCreateForm(forms.ModelForm):
    email = forms.EmailField(label='Team member email')
    full_name = forms.CharField(max_length=150)
    password1 = forms.CharField(label='Initial password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm initial password', widget=forms.PasswordInput)
    access_level = forms.ChoiceField(
        label='Access level',
        choices=((PlatformTeamMember.ACCESS_LEVEL_READ_ONLY, 'Read-only'),),
        initial=PlatformTeamMember.ACCESS_LEVEL_READ_ONLY,
        disabled=True,
    )

    class Meta:
        model = PlatformTeamMember
        fields = ('access_level',)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('An account with this email already exists.')
        return email

    def clean_full_name(self):
        full_name = ' '.join(self.cleaned_data['full_name'].split())
        if not full_name:
            raise ValidationError('Enter the team member’s full name.')
        return full_name

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'The passwords do not match.')
        elif password1:
            try:
                validate_password(password1)
            except ValidationError as exc:
                self.add_error('password1', exc)
        return cleaned_data


def _team_login_username(email):
    # Prefer email for a familiar admin sign-in. Fall back to a generated
    # username only if an existing account already uses it as its username.
    candidate = email.lower()
    if len(candidate) <= 150 and not User.objects.filter(username__iexact=candidate).exists():
        return candidate

    base = slugify(email.partition('@')[0])[:100] or 'team'
    candidate = f'{base}-team-{uuid.uuid4().hex[:10]}'
    while User.objects.filter(username__iexact=candidate).exists():
        candidate = f'{base}-team-{uuid.uuid4().hex[:10]}'
    return candidate


def _set_platform_read_only_permissions(user):
    view_models = (
        ('users', 'user'),
        ('admin_dashboard', 'loginactivity'),
        ('admin_dashboard', 'sociallink'),
        ('admin_dashboard', 'platformteammember'),
    )
    permissions = []
    for app_label, model_name in view_models:
        content_type = ContentType.objects.get(app_label=app_label, model=model_name)
        permissions.append(Permission.objects.get(
            content_type=content_type,
            codename=f'view_{model_name}',
        ))
    user.groups.clear()
    user.user_permissions.set(permissions)


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


@admin.register(PlatformTeamMember)
class PlatformTeamMemberAdmin(admin.ModelAdmin):
    """Maintain a separate roster for RichLead platform staff."""

    list_display = ('team_name', 'email', 'login_username', 'access_level', 'is_active', 'last_login', 'created_at')
    list_filter = ('access_level', 'is_active')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'user__username')
    ordering = ('access_level', 'user__email')
    fields = ('user', 'access_level', 'is_active', 'created_by', 'created_at', 'updated_at')

    @admin.display(description='Team member', ordering='user__first_name')
    def team_name(self, member):
        return member.user.get_full_name().strip() or member.user.email

    @admin.display(description='Email', ordering='user__email')
    def email(self, member):
        return member.user.email

    @admin.display(description='Admin login username', ordering='user__username')
    def login_username(self, member):
        return member.user.username

    @admin.display(description='Last sign-in', ordering='user__last_login')
    def last_login(self, member):
        return member.user.last_login

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'created_by')

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            return PlatformTeamMemberCreateForm
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return ((None, {'fields': ('email', 'full_name', 'password1', 'password2', 'access_level')}),)
        return super().get_fieldsets(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ('created_by', 'created_at', 'updated_at')
        fields = ('user', 'access_level', 'created_by', 'created_at', 'updated_at')
        if obj.access_level == PlatformTeamMember.ACCESS_LEVEL_SUPER_ADMIN:
            return fields + ('is_active',)
        return fields

    def has_module_permission(self, request):
        return bool(request.user.is_superuser or request.user.has_perm('admin_dashboard.view_platformteammember'))

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_superuser or request.user.has_perm('admin_dashboard.view_platformteammember'))

    def has_add_permission(self, request):
        return bool(request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        if not request.user.is_superuser:
            return False
        return obj is None or obj.access_level == PlatformTeamMember.ACCESS_LEVEL_READ_ONLY

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            if not change:
                email = form.cleaned_data['email']
                first_name, _, last_name = form.cleaned_data['full_name'].partition(' ')
                user = User(
                    username=_team_login_username(email),
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    is_staff=True,
                    is_active=True,
                    is_superuser=False,
                )
                user.set_password(form.cleaned_data['password1'])
                user.save()
                obj.user = user
                obj.access_level = PlatformTeamMember.ACCESS_LEVEL_READ_ONLY
                obj.is_active = True
                obj.created_by = request.user
                super().save_model(request, obj, form, change)
                _set_platform_read_only_permissions(user)
                self.message_user(
                    request,
                    f'Read-only team account created. Admin login username: {user.username}',
                    messages.SUCCESS,
                )
                return

            super().save_model(request, obj, form, change)
            if obj.access_level == PlatformTeamMember.ACCESS_LEVEL_READ_ONLY:
                user = obj.user
                user.is_staff = True
                user.is_superuser = False
                user.is_active = obj.is_active
                user.save(update_fields=('is_staff', 'is_superuser', 'is_active'))
                _set_platform_read_only_permissions(user)
