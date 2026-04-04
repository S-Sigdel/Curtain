from peewee import AutoField, CharField, DateTimeField, ForeignKeyField, TextField

from app.database import BaseModel
from app.models.url import Url
from app.models.user import User


class Event(BaseModel):
    # Auto-increment for new events while preserving imported IDs from the seed files.
    id = AutoField()
    url = ForeignKeyField(Url, backref="events", column_name="url_id", null=True)
    # Some event rows may not be attributable to a specific authenticated user.
    user = ForeignKeyField(User, backref="events", column_name="user_id", null=True)
    event_type = CharField(max_length=64)
    timestamp = DateTimeField()
    details = TextField()

    class Meta:
        table_name = "events"
