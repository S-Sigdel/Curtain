# Import your models here so Peewee registers them.
# Example:
#   from app.models.product import Product

from app.models.event import Event
from app.models.url import Url
from app.models.user import User

MODELS = [User, Url, Event]
