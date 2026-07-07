from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'username',
        'display_name_column',
        'email',
        'role',
        'is_active',
        'is_staff',
        'last_login',
    )
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'name', 'email', 'phone')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('LMS 정보', {'fields': ('name', 'phone', 'role')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('LMS 정보', {'fields': ('name', 'phone', 'role')}),
    )

    @admin.display(description='이름')
    def display_name_column(self, obj):
        return obj.display_name
