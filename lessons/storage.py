from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateVideoStorage(FileSystemStorage):
    """File storage for lesson videos that must not expose a public URL."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('location', settings.PRIVATE_MEDIA_ROOT)
        super().__init__(*args, **kwargs)

    def url(self, name):
        raise ValueError('Private lesson videos do not have public URLs.')


private_video_storage = PrivateVideoStorage()
