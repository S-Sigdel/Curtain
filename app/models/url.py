from peewee import AutoField, BooleanField, CharField, DateTimeField, ForeignKeyField

from app.database import BaseModel
from app.models.user import User


class Url(BaseModel):
    # Auto-increment for new rows after the seeded CSV data has been loaded.
    id = AutoField()
    # URLs may exist without an owning user in local testing or unauthenticated flows.
    user = ForeignKeyField(User, backref="urls", column_name="user_id", null=True)
    short_code = CharField(max_length=16, unique=True, index=True)
    original_url = CharField(max_length=2048)
    title = CharField(max_length=255, null=True)
    is_active = BooleanField(default=True)
    created_at = DateTimeField()
    updated_at = DateTimeField()

    class Meta:
        table_name = "urls"
