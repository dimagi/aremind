import re

from django.core.exceptions import ValidationError
from rapidsms.models import Contact

_ = lambda s: s
phone_re = re.compile(r"\d{1,3}\d{10}$")

def validate_phone(value):
    """ Require country code followed by 10 digits """
    if not phone_re.match(value):
        msg = 'Please enter a number in a format like: XXXYYYZZZZZZZ'
        raise ValidationError(msg)


"""
This function will raise an exception if a Contact entry
exists with the given phone number, excluding the Contact
with the given primary key id.
"""
def validate_unique_phone(phone_num, excluded_contact_id):
    if Contact.objects.exclude(id = excluded_contact_id).filter(phone = phone_num).count() > 0:
       raise ValidationError(_("Another contact already exists with this phone number."))

