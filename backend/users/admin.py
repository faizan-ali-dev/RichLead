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
from django.utils.html import format_html_join
from django.utils.text import slugify

User = get_user_model()


class PlatformTeamMemberCreateForm(forms.ModelForm):
    email = forms.EmailField(label='Team member email')
    full_name = forms.CharField(max_length=150)
    password1 = forms.CharField(label='Initial password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm initial password', widget=forms.PasswordInput)
    access_level = forms.ChoiceField(
        label='Access level',
        choices=PlatformTeamMember.ACCESS_LEVEL_CHOICES,
        initial=PlatformTeamMember.ACCESS_LEVEL_READ_ONLY,
        help_text='Super admin grants full control of Django admin and the SaaS admin dashboard.',
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


class PlatformTeamMemberEditForm(forms.ModelForm):
    full_name = forms.CharField(label='Full name', max_length=150, required=False)

    class Meta:
        model = PlatformTeamMember
        fields = ('access_level', 'is_active')

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.fields['full_name'].initial = self.instance.user.get_full_name().strip()
        self.fields['access_level'].help_text = (
            'Super admin can access Django admin and the SaaS admin dashboard. '
            'Read-only can inspect the permitted platform overview only.'
        )

    def clean_full_name(self):
        return ' '.join(self.cleaned_data.get('full_name', '').split())

    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk or not self.request:
            return cleaned_data

        new_access_level = cleaned_data.get('access_level', self.instance.access_level)
        new_is_active = cleaned_data.get('is_active', self.instance.is_active)
        changes_privilege = (
            new_access_level != PlatformTeamMember.ACCESS_LEVEL_SUPER_ADMIN or not new_is_active
        )
        if self.instance.user_id == self.request.user.pk and changes_privilege:
            self.add_error('access_level', 'You cannot remove your own active super-admin access.')
        elif (
            self.instance.access_level == PlatformTeamMember.ACCESS_LEVEL_SUPER_ADMIN
            and changes_privilege
            and not PlatformTeamMember.objects.filter(
                access_level=PlatformTeamMember.ACCESS_LEVEL_SUPER_ADMIN,
                is_active=True,
            ).exclude(pk=self.instance.pk).exists()
        ):
            self.add_error('access_level', 'Keep at least one active super admin on the platform.')
        return cleaned_data


class CustomerAccountCreateForm(forms.ModelForm):
    email = forms.EmailField(label='Email address')
    full_name = forms.CharField(max_length=150)
    password1 = forms.CharField(label='Initial password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm initial password', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ('email', 'nickname', 'email_verified', 'is_active')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('An account with this email already exists.')
        return email

    def clean_full_name(self):
        full_name = ' '.join(self.cleaned_data['full_name'].split())
        if not full_name:
            raise ValidationError('Enter the customer’s full name.')
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

    def save(self, commit=True):
        user = super().save(commit=False)
        email = self.cleaned_data['email']
        first_name, _, last_name = self.cleaned_data['full_name'].partition(' ')
        user.email = email
        user.username = _account_login_username(email)
        user.first_name = first_name
        user.last_name = last_name
        user.nickname = self.cleaned_data.get('nickname', '')
        user.is_staff = False
        user.is_superuser = False
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


def _account_login_username(email):
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
    readonly_fields = ('username', 'email', 'date_joined', 'last_login', 'product_adoption_summary')
    actions = ('activate_customer_accounts', 'deactivate_customer_accounts')

    @admin.display(description='Name', ordering='first_name')
    def display_name(self, user):
        return user.get_full_name().strip() or user.nickname or 'Unnamed user'

    def get_queryset(self, request):
        # Platform administrators are not customer accounts and must not be
        # suspendable from the customer-management table.
        return super().get_queryset(request).filter(is_staff=False, is_superuser=False)

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            return CustomerAccountCreateForm
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                ('Customer account', {'fields': ('email', 'full_name', 'nickname', 'password1', 'password2')}),
                ('Access', {'fields': ('is_active', 'email_verified')}),
            )
        return (
            ('Account', {'fields': ('username', 'email', 'date_joined', 'last_login')}),
            ('Profile', {'fields': ('first_name', 'last_name', 'nickname')}),
            ('Access', {'fields': ('is_active', 'email_verified')}),
            ('Product adoption', {'fields': ('product_adoption_summary',)}),
        )

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return self.readonly_fields

    def has_add_permission(self, request):
        return bool(request.user.is_superuser)

    @admin.display(description='Product setup and recent activity')
    def product_adoption_summary(self, user):
        from admin_dashboard.services import user_adoption

        adoption = user_adoption([user.pk])[user.pk]
        profile = adoption['business_profile']
        llm = adoption['llm']
        llm_value = ', '.join(llm['providers']) or ('Paused' if llm['configured_providers'] else 'Not configured')
        rows = (
            f"Business profile: {profile['status'].replace('_', ' ').title()}; ICP: {'configured' if profile['icp_configured'] else 'not configured'}",
            f"LLM providers: {llm_value}",
            f"Apollo: {adoption['apollo']['status'].title()}, {adoption['apollo']['runs_30d']} searches in 30 days",
            f"Hunter: {adoption['hunter']['status'].title()}, {adoption['hunter']['runs_30d']} searches in 30 days",
            f"Connected mailboxes: {adoption['mailbox']['connected_count']}",
            f"AI workflow runs: {adoption['ai_activity']['runs_30d']} in 30 days",
        )
        return format_html_join('', '<div>{}</div>', ((row,) for row in rows))

    @admin.action(description='Activate selected customer accounts')
    def activate_customer_accounts(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} account(s) activated.', messages.SUCCESS)

    @admin.action(description='Suspend selected customer accounts')
    def deactivate_customer_accounts(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} account(s) suspended. Their workspace data was retained.', messages.SUCCESS)

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

        class RequestAwareEditForm(PlatformTeamMemberEditForm):
            def __init__(self, *args, **form_kwargs):
                form_kwargs['request'] = request
                super().__init__(*args, **form_kwargs)

        return RequestAwareEditForm

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return ((None, {'fields': ('email', 'full_name', 'password1', 'password2', 'access_level')}),)
        return ((None, {'fields': ('full_name', 'access_level', 'is_active')}), ('Record', {'fields': ('user', 'created_by', 'created_at', 'updated_at')}))

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ('created_by', 'created_at', 'updated_at')
        return ('user', 'created_by', 'created_at', 'updated_at')

    def has_module_permission(self, request):
        return bool(request.user.is_superuser or request.user.has_perm('admin_dashboard.view_platformteammember'))

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_superuser or request.user.has_perm('admin_dashboard.view_platformteammember'))

    def has_add_permission(self, request):
        return bool(request.user.is_superuser)

    def has_change_permission(self, request, obj=None):
        return bool(request.user.is_superuser)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            if not change:
                email = form.cleaned_data['email']
                first_name, _, last_name = form.cleaned_data['full_name'].partition(' ')
                access_level = form.cleaned_data['access_level']
                user = User(
                    username=_account_login_username(email),
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
                obj.access_level = access_level
                obj.is_active = True
                obj.created_by = request.user
                super().save_model(request, obj, form, change)
                if access_level == PlatformTeamMember.ACCESS_LEVEL_SUPER_ADMIN:
                    user.is_superuser = True
                    user.save(update_fields=('is_superuser',))
                else:
                    _set_platform_read_only_permissions(user)
                self.message_user(
                    request,
                    f'{obj.get_access_level_display()} team account created. Admin login username: {user.username}',
                    messages.SUCCESS,
                )
                return

            super().save_model(request, obj, form, change)
            user = obj.user
            full_name = form.cleaned_data.get('full_name', '') if form is not None else ''
            if full_name:
                user.first_name, _, user.last_name = full_name.partition(' ')
            user.is_staff = True
            user.is_superuser = obj.access_level == PlatformTeamMember.ACCESS_LEVEL_SUPER_ADMIN
            user.is_active = obj.is_active
            user.save(update_fields=('first_name', 'last_name', 'is_staff', 'is_superuser', 'is_active'))
            if obj.access_level == PlatformTeamMember.ACCESS_LEVEL_READ_ONLY:
                _set_platform_read_only_permissions(user)
            else:
                user.groups.clear()
                user.user_permissions.clear()
