from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateCertificateAssetStorage(FileSystemStorage):
    """Private storage for certificate logo and seal assets."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('location', settings.PRIVATE_MEDIA_ROOT)
        super().__init__(*args, **kwargs)

    def url(self, name):
        raise ValueError('Certificate design assets do not have public URLs.')


private_certificate_asset_storage = PrivateCertificateAssetStorage()
