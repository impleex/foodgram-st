import base64
import uuid

from django.core.files.base import ContentFile
from rest_framework import serializers


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and "base64" in data:
            header, base64_string = data.split(";base64,")
            try:
                decoded_file = base64.b64decode(base64_string)
            except TypeError:
                raise serializers.ValidationError("Невалидная base64-строка")

            file_name = str(uuid.uuid4())[:12]
            file_extension = "png"
            complete_file_name = f"{file_name}.{file_extension}"

            return ContentFile(decoded_file, name=complete_file_name)

        return super().to_internal_value(data)
