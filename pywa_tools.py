from pywa import WhatsApp
from pywa.types.templates import TemplateLanguage
## URL: https://gladys-tetrarchic-dovie.ngrok-free.dev/webhook/

TOKEN = "EAATYGW2lhwgBQ4NNpLFVOzkhBCfH7SeWuus3RkF47cq9ldlK7QnU9UHhYZAH9xfWlOnf6p3sbbZAZC179mGXxiS6ZBLRt0EU5bWPrkjLOsjP1mAWVrPR8xadDOnEOWDuyhD0SFhojrOpqcKoo68NzqNdtJMGNqdoKEAZCGP1xdD1EMVn6J2CY86XZCWe30HQZDZD"

PHONE_NUMBER_ID = "954435134428733"

wa = WhatsApp(
    token=TOKEN,
    phone_id=PHONE_NUMBER_ID
)

wa.send_template(
    to="5571994111866",
    name="evento_supera",
    language=TemplateLanguage("en_US")
)

wa.send_message(
    to="5571994111866",
    text="oi",
)

# Inicialize o cliente