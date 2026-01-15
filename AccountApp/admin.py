from django.contrib import admin
from .models import db_Profile , Player , Transaction

class db_Profile_Item(admin.ModelAdmin):
    list_display = ('auth_token' , 'email', 'db_phone_number', 'username', 'code_pin', 'db_fullname', 'is_verified', 'is_staff' , 'db_country_address',  'expired_time_end',)
    readonly_fields = (  'created_at', )


admin.site.register(db_Profile, db_Profile_Item) 
admin.site.register(Player)
admin.site.register(Transaction) 
 