import os

from .exceptions import ImproperlyConfigured


class Settings:

    BASE_DIR = os.curdir
    SECRET_KEY = ""
    MEDIA_DIR = "media"
    WORK_DIR = "work_dir"
    SERVICE_INI = os.path.join("config", "services.ini")
    SERVICES = ()

    def __init__(self, settings_module):
        """
        :param settings_module: module where constants are loaded from
        """
        # load settings from the `settings_module`
        for field in dir(settings_module):
            if field.isupper():
                setattr(self, field, getattr(settings_module, field))

        if not os.path.isabs(self.BASE_DIR):
            self.BASE_DIR = os.path.join(
                settings_module.__file__, self.BASE_DIR
            )

        if not self.SECRET_KEY:
            raise ImproperlyConfigured("Field SECRET_KEY is not set.")

        if not os.path.isabs(self.MEDIA_DIR):
            self.MEDIA_DIR = os.path.join(self.BASE_DIR, self.MEDIA_DIR)
        os.makedirs(self.MEDIA_DIR, exist_ok=True)

        if not os.path.isabs(self.WORK_DIR):
            self.WORK_DIR = os.path.join(self.BASE_DIR, self.WORK_DIR)
        os.makedirs(self.WORK_DIR, exist_ok=True)

        if self.SERVICE_INI is not None:
            if not os.path.isabs(self.SERVICE_INI):
                self.SERVICE_INI = os.path.join(self.BASE_DIR, self.SERVICE_INI)
            if not os.path.isfile(self.SERVICE_INI):
                raise ImproperlyConfigured(
                    "{} is not a file.".format(self.SERVICE_INI)
                )

        if not isinstance(self.SERVICES, (tuple, list)):
            raise ImproperlyConfigured(
                "SERVICES must be a list or tuple of service names"
            )