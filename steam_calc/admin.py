# steam_calc/admin.py
from django.contrib import admin
from .models import SteamQueryLog

@admin.register(SteamQueryLog)
class SteamQueryLogAdmin(admin.ModelAdmin):
    # Columns to display in the admin list view
    list_display = ('pressure', 'temperature', 'is_valid', 'timestamp')
    
    # Adds a filter sidebar
    list_filter = ('is_valid', 'timestamp')
    
    # Adds a search bar (useful if you have thousands of entries)
    search_fields = ('pressure', 'temperature')
    
    # Default sorting (newest first)
    ordering = ('-timestamp',)