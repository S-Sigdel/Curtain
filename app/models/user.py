from peewee import AutoField, CharField, DateTimeField

from app.database import BaseModel


class User(BaseModel):
    # Auto-increment for app-created users while still allowing explicit IDs from CSV seeds.
    id = AutoField()
    username = CharField(max_length=120)
    email = CharField(max_length=255, unique=True)
    created_at = DateTimeField()

    class Meta:
        table_name = "users"
